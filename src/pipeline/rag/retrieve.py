try:
    from src.pipeline.rag.legal_rag.cli_retrieve import main
except ModuleNotFoundError:
    from legal_rag.cli_retrieve import main


if __name__ == "__main__":
    main()
