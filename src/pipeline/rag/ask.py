try:
    from src.pipeline.rag.legal_generator.cli_ask import main
except ModuleNotFoundError:
    from legal_generator.cli_ask import main

if __name__ == "__main__":
    main()
