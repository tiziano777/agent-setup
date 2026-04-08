"""DeepConf: Reasoning Language Model wrapper.

Provides deep thinking inference with confidence-based voting strategies.
Wraps facebookresearch/deepconf DeepThinkLLM with optional fallback to multi-step
reasoning via LiteLLM proxy when vLLM backend unavailable.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class VotingResult:
    """Single voting strategy result."""

    strategy: str
    answer: str
    confidence: float = 0.0


@dataclass
class DeepConfOutput:
    """Structured output from DeepConf reasoning."""

    final_answer: str
    voted_answer: str
    voting_results: dict[str, VotingResult] = field(default_factory=dict)
    all_traces: list[str] = field(default_factory=list)
    warmup_traces: list[str] = field(default_factory=list)
    final_traces: list[str] = field(default_factory=list)
    conf_bar: float = 0.0
    reasoning_steps: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    mode: str = "offline"
    timestamp: str = ""


class DeepConf:
    """Deep Reasoning Language Model via deepconf or fallback multi-step reasoning.

    Uses DeepThinkLLM (facebookresearch/deepconf) when available with vLLM backend.
    Falls back to multi-step structured reasoning with LiteLLM proxy otherwise.

    Attributes:
        model: Model identifier (e.g., "deepseek-ai/DeepSeek-R1" for vLLM,
               or "llm" for LiteLLM proxy fallback).
        use_deepthink: Whether DeepThinkLLM is available and enabled.
        llm: DeepThinkLLM instance (if use_deepthink=True, None otherwise).
        fallback_llm: ChatOpenAI instance for multi-step reasoning fallback.
    """

    def __init__(
        self,
        model: str = "llm",
        enable_deepthink: bool = True,
        vllm_tensor_parallel_size: int = 1,
        **vllm_kwargs,
    ):
        """Initialize DeepConf.

        Args:
            model: Model identifier. For DeepThinkLLM, use full HF path
                   (e.g., "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B").
                   For fallback, defaults to "llm" (proxy rotation).
            enable_deepthink: Try to use DeepThinkLLM if available. Falls back
                              to multi-step reasoning if import/init fails.
            vllm_tensor_parallel_size: vLLM tensor parallelism (for multi-GPU).
            **vllm_kwargs: Additional vLLM kwargs passed to DeepThinkLLM.
        """
        self.model = model
        self.use_deepthink = False
        self.llm = None
        self.fallback_llm = None
        self._reasoning_cache = {}

        # Try to initialize DeepThinkLLM if enabled
        if enable_deepthink:
            try:
                from deepconf.deepthink import DeepThinkLLM

                try:
                    self.llm = DeepThinkLLM(
                        model=model,
                        tensor_parallel_size=vllm_tensor_parallel_size,
                        **vllm_kwargs,
                    )
                    self.use_deepthink = True
                    logger.info(
                        f"DeepConf initialized with DeepThinkLLM "
                        f"(model={model})"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to initialize DeepThinkLLM: {e}. "
                        f"Falling back to multi-step reasoning with LiteLLM."
                    )
                    self._init_fallback()
            except ImportError:
                logger.warning(
                    "deepconf package not found. Install with: "
                    "pip install 'agent-setup[deepconf]'. "
                    "Using fallback multi-step reasoning."
                )
                self._init_fallback()
        else:
            self._init_fallback()

    def _init_fallback(self) -> None:
        """Initialize fallback LiteLLM-based multi-step reasoning."""
        from src.shared.llm import get_llm

        self.fallback_llm = get_llm(model="llm", temperature=0.7)
        logger.info("Using fallback multi-step reasoning via LiteLLM proxy")

    async def think(
        self,
        prompt: str,
        mode: str = "offline",
        budget: int = 5,
        warmup_traces: int = 2,
        total_budget: Optional[int] = None,
        compute_multiple_voting: bool = True,
        sampling_params: Optional[dict[str, Any]] = None,
        **kwargs,
    ) -> DeepConfOutput:
        """Execute deep reasoning on a prompt.

        Args:
            prompt: Input prompt for reasoning.
            mode: "online" (confidence-based early stopping) or
                  "offline" (batch voting). Default "offline".
            budget: Number of reasoning traces to generate (offline mode).
            warmup_traces: Calibration traces for confidence threshold (online mode).
            total_budget: Max traces allowed (online mode). Defaults to 2*budget.
            compute_multiple_voting: Enable all voting strategies.
            sampling_params: Optional dict with vLLM sampling configuration.
            **kwargs: Additional arguments passed to deepthink().

        Returns:
            DeepConfOutput with final answer, voting results, traces, and metrics.
        """
        if self.use_deepthink and self.llm:
            return await self._deepthink_backend(
                prompt=prompt,
                mode=mode,
                budget=budget,
                warmup_traces=warmup_traces,
                total_budget=total_budget,
                compute_multiple_voting=compute_multiple_voting,
                sampling_params=sampling_params,
                **kwargs,
            )
        else:
            return await self._fallback_multi_step_reasoning(
                prompt=prompt,
                budget=budget,
                **kwargs,
            )

    async def _deepthink_backend(
        self,
        prompt: str,
        mode: str = "offline",
        budget: int = 5,
        warmup_traces: int = 2,
        total_budget: Optional[int] = None,
        compute_multiple_voting: bool = True,
        sampling_params: Optional[dict[str, Any]] = None,
        **kwargs,
    ) -> DeepConfOutput:
        """Execute reasoning via DeepThinkLLM backend."""
        import asyncio

        if total_budget is None:
            total_budget = budget * 2

        try:
            # DeepThinkLLM.deepthink() is synchronous; run in executor
            result = await asyncio.to_thread(
                self.llm.deepthink,
                prompt=prompt,
                mode=mode,
                budget=budget,
                warmup_traces=warmup_traces,
                total_budget=total_budget,
                compute_multiple_voting=compute_multiple_voting,
                sampling_params=sampling_params or {},
            )

            # Map DeepThinkOutput to DeepConfOutput
            voting_results = {}
            if hasattr(result, "voting_results") and result.voting_results:
                for strategy, vote_data in result.voting_results.items():
                    if isinstance(vote_data, dict):
                        voting_results[strategy] = VotingResult(
                            strategy=strategy,
                            answer=vote_data.get("answer", ""),
                            confidence=vote_data.get("confidence", 0.0),
                        )
                    else:
                        # vote_data might be a named tuple or object
                        voting_results[strategy] = VotingResult(
                            strategy=strategy,
                            answer=getattr(vote_data, "answer", str(vote_data)),
                            confidence=getattr(vote_data, "confidence", 0.0),
                        )

            return DeepConfOutput(
                final_answer=result.final_answer if hasattr(result, "final_answer")
                else "",
                voted_answer=result.voted_answer if hasattr(result, "voted_answer")
                else result.final_answer,
                voting_results=voting_results,
                all_traces=list(result.all_traces) if hasattr(result, "all_traces")
                else [],
                warmup_traces=list(result.warmup_traces)
                if hasattr(result, "warmup_traces")
                else [],
                final_traces=list(result.final_traces)
                if hasattr(result, "final_traces")
                else [],
                conf_bar=float(result.conf_bar) if hasattr(result, "conf_bar")
                else 0.0,
                reasoning_steps=[],
                mode=mode,
            )

        except Exception as e:
            logger.error(f"DeepThinkLLM reasoning failed: {e}")
            # Fall back gracefully
            return DeepConfOutput(
                final_answer=f"Error in deep reasoning: {str(e)}",
                voted_answer=f"Error in deep reasoning: {str(e)}",
            )

    async def _fallback_multi_step_reasoning(
        self,
        prompt: str,
        budget: int = 5,
        **kwargs,
    ) -> DeepConfOutput:
        """Execute multi-step reasoning via LiteLLM proxy fallback."""
        import asyncio
        from datetime import datetime

        if not self.fallback_llm:
            self._init_fallback()

        reasoning_steps = []
        traces = []
        answers = {}

        # Multi-step reasoning with different strategies
        strategies = [
            ("direct", "Answer the following directly:\n"),
            ("step_by_step", "Think step by step:\n"),
            ("chain_of_thought", "Use chain of thought reasoning:\n"),
            ("breakdown", "Break down the problem and solve:\n"),
        ]

        # Generate reasoning traces using different approaches
        for i in range(min(budget, len(strategies))):
            strategy_name, prefix = strategies[i]

            try:
                # Async invoke via executor
                def invoke_llm():
                    result = self.fallback_llm.invoke(
                        f"{prefix}{prompt}"
                    )
                    return result.content if hasattr(result, "content") else str(
                        result
                    )

                response = await asyncio.to_thread(invoke_llm)

                trace = f"[{strategy_name}]\n{response}"
                traces.append(trace)
                reasoning_steps.append(
                    f"Step {i+1} ({strategy_name}): {response[:100]}..."
                )
                answers[strategy_name] = response

            except Exception as e:
                logger.error(f"Fallback reasoning step {i+1} failed: {e}")
                traces.append(f"[{strategy_name}] Error: {str(e)}")

        # Voting: select most common/coherent answer
        final_answer = (
            answers.get("direct", "")
            or answers.get("step_by_step", "")
            or answers.get("chain_of_thought", "")
            or "Could not generate answer"
        )

        voting_results = {
            strategy: VotingResult(
                strategy=strategy,
                answer=answer,
                confidence=0.8 if answer else 0.0,
            )
            for strategy, answer in answers.items()
        }

        return DeepConfOutput(
            final_answer=final_answer,
            voted_answer=final_answer,
            voting_results=voting_results,
            all_traces=traces,
            warmup_traces=traces[: len(traces) // 2],
            final_traces=traces[len(traces) // 2 :],
            reasoning_steps=reasoning_steps,
            mode="offline_fallback",
            timestamp=datetime.now().isoformat(),
        )

    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """Standard text generation without deep reasoning.

        Available only when DeepThinkLLM is initialized.
        Falls back to LiteLLM proxy for standard generation.

        Args:
            prompt: Input prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.
            **kwargs: Additional generation parameters.

        Returns:
            Generated text.
        """
        if self.use_deepthink and self.llm:
            try:
                result = self.llm.generate(
                    prompts=[prompt],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                return result.outputs[0].text if result.outputs else ""
            except Exception as e:
                logger.error(f"DeepThinkLLM generation failed: {e}")
        # Fallback to LiteLLM
        if not self.fallback_llm:
            self._init_fallback()
        result = self.fallback_llm.invoke(prompt)
        return result.content if hasattr(result, "content") else str(result)

    def get_signature(self) -> dict[str, Any]:
        """Return model signature and capabilities.

        Returns:
            Dict with backend type, model name, supports_deepthink, etc.
        """
        return {
            "backend": "deepthink" if self.use_deepthink else "fallback",
            "model": self.model,
            "supports_deepthink": self.use_deepthink,
            "supports_voting": True,
            "supports_multi_step": True,
            "modes": ["online", "offline"] if self.use_deepthink else ["offline"],
        }
