import asyncio

async def main():
    import cognee
    from src.shared.cognee_toolkit import CogneeSettings, setup_cognee

    settings = CogneeSettings(default_dataset="test_pgvector")
    setup_cognee(settings=settings)

    print("=== Pruning existing data ===")
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(graph=True, vector=True)

    print("=== Adding document ===")
    await cognee.add(
        "SynthEx Corp is a company founded in 2022 in Zurich by Markus Heller. "
        "It raised 320 million dollars in Series C funding led by Horizon Ventures.",
        dataset_name="test_pgvector",
    )

    print("=== Running cognify ===")
    await cognee.cognify()

    print("=== Searching ===")
    results = await cognee.search("What is SynthEx?", search_type="CHUNKS")
    print(f"Results: {len(results)}")
    for r in results[:3]:
        print(f"  - {str(r)[:200]}")

    print("=== Cleanup ===")
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(graph=True, vector=True)
    print("=== DONE ===")

asyncio.run(main())
