# Legal Parser

Module parser van ban phap luat Viet Nam tu `.docx`/`.doc` sang du lieu cau truc.

## Entry Points

- `parse_main_body.py`: parse phan than van ban chinh.
- `parse_attachments.py`: parse rieng phu luc/mau/QCVN dinh kem.
- `parse_package.py`: parse mot package gom van ban chinh va cac file dinh kem.

## Cau Truc

```text
src/pipeline/data_preprocessing/parser/
  parse_main_body.py
  parse_attachments.py
  parse_package.py
  requirements.txt
  README.md
  legal_parser/
    body/
    attachments/
    package/
    common/
```

## Cai Dat

```powershell
pip install -r src\pipeline\data_preprocessing\parser\requirements.txt
```

Parser doc `.docx` bang `python-docx`/`mammoth`. Voi file `.doc`, CLI co the tu chuyen sang `.docx` truoc khi parse neu moi truong ho tro converter.

## Chay Parser

Parse mot package:

```powershell
python src\pipeline\data_preprocessing\parser\parse_package.py `
  --input data\dataset\119_2024_NDCP `
  --output data\preprocessed\parsed
```

Parse toan bo dataset:

```powershell
python src\pipeline\data_preprocessing\parser\parse_package.py `
  --input data\dataset `
  --output data\preprocessed\parsed `
  --no-convert-doc
```

## Dung Nhu Package

```python
from src.pipeline.data_preprocessing.parser.legal_parser.body.parser import LegalBodyParser
from src.pipeline.data_preprocessing.parser.legal_parser.package.parser import LegalPackageParser
from src.pipeline.data_preprocessing.parser.legal_parser.common.models import ParserConfig
```
