try:
    from pipeline.data_preprocessing.effectivity.legal_effectivity.cli import main
except ModuleNotFoundError:
    try:
        from src.pipeline.data_preprocessing.effectivity.legal_effectivity.cli import main
    except ModuleNotFoundError:
        from legal_effectivity.cli import main

if __name__ == "__main__":
    main()
