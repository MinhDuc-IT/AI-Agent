try:
    from agent.data_preprocessing.chunker.legal_chunker.cli import main
except ModuleNotFoundError:
    try:
        from src.pipeline.data_preprocessing.chunker.legal_chunker.cli import main
    except ModuleNotFoundError:
        from legal_chunker.cli import main

if __name__ == "__main__":
    main()
