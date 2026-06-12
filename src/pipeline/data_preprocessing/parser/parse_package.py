try:
    from agent.data_preprocessing.parser.legal_parser.package.cli import main
except ModuleNotFoundError:
    try:
        from src.pipeline.data_preprocessing.parser.legal_parser.package.cli import main
    except ModuleNotFoundError:
        from legal_parser.package.cli import main


if __name__ == "__main__":
    main()
