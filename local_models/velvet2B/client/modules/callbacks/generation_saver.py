
from transformers import TrainerCallback
import json
import random
import torch
from datetime import datetime
from pathlib import Path

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GenerationSaverCallback — generates K eval samples and saves to JSONL
# ---------------------------------------------------------------------------

class GenerationSaverCallback(TrainerCallback):
    """Periodically generates responses from eval prompts, logs and saves to JSONL."""

    def __init__(
        self,
        model,
        tokenizer,
        eval_dataset,
        model_name: str,
        output_dir: str = "modules/docs/generations",
        num_samples: int = 3,
        log_steps_interval: int = 500,
        max_new_tokens: int = 1024,
    ):
        self.model = model
        self.tokenizer = tokenizer
        self.eval_dataset = eval_dataset
        self.model_name = model_name
        self.output_dir = Path(output_dir)
        self.num_samples = num_samples
        self.log_steps_interval = log_steps_interval
        self.max_new_tokens = max_new_tokens

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def on_log(self, args, state, control, **kwargs):
        if state.global_step == 0:
            return
        if state.global_step % self.log_steps_interval != 0:
            return
        self._generate_samples(state.global_step)

    def _generate_samples(self, step: int):
        """Generate K samples from eval dataset and save to JSONL."""
        if self.eval_dataset is None or len(self.eval_dataset) == 0:
            return

        n = min(self.num_samples, len(self.eval_dataset))
        indices = random.sample(range(len(self.eval_dataset)), n)

        logger.info("=" * 80)
        logger.info("GENERATION SAMPLES @ step %d", step)
        logger.info("=" * 80)

        records = []
        self.model.eval()
        for i, idx in enumerate(indices):
            sample = self.eval_dataset[idx]
            prompt = sample["prompt"]
            chosen = sample["chosen"]

            # Tokenize prompt
            prompt_text = prompt if isinstance(prompt, str) else self.tokenizer.apply_chat_template(prompt, tokenize=False, add_generation_prompt=True)
            inputs = self.tokenizer(
                prompt_text,
                return_tensors="pt",
                truncation=True,
            ).to(self.model.device)

            with torch.no_grad():
                output_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=self.max_new_tokens,
                    do_sample=False,
                    temperature=1.0,
                )

            # Decode only the generated part
            generated_ids = output_ids[0][inputs["input_ids"].shape[1]:]
            generated_text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)

            chosen_text = chosen if isinstance(chosen, str) else str(chosen)

            records.append({
                "prompt": prompt_text,
                "gold": chosen_text,
                "generated": generated_text,
            })

            logger.info("-" * 40)
            logger.info("Sample %d/%d", i + 1, n)
            logger.info("PROMPT: %s", prompt_text[:200])
            logger.info("GOLD (chosen): %s", chosen_text[:500])
            logger.info("GENERATED:     %s", generated_text[:500])

        logger.info("=" * 80)
        self.model.train()

        # Save to JSONL
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.model_name}_{step}_{ts}.jsonl"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        logger.info("Generations saved to %s", filepath)
