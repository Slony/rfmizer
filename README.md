# RFMizer

## Системные требования

- Python 2.7
- Установленный пакет `pyyaml`

Для установки `pyyaml` используйте [pip](https://pip.pypa.io/en/stable/installing/):

```
sudo pip install --user pyyaml
```

или

```
pip install --user pyyaml
```


## Использование

```
python rfmizer.py [--log-level LOG_LEVEL] config-file input-file
```

Обязательные аргументы:

- `config-file` — конфигурационный файл в формате [Yaml](http://yaml.org/)
- `input-file` — файл с информацией о заказах в формате [CSV](https://tools.ietf.org/html/rfc4180)

Необязательные аргументы:

- `--log-level LOG_LEVEL` — минимальный уровень сообщений, выдаваемых в процессе исполнения; возможные значения:
  - `CRITICAL`;
  - `ERROR`;
  - `WARNING` (уровень сообщений по умолчанию);
  - `INFO`;
  - `DEBUG`. 
  
`python rfmizer.py -h` отображает подсказку по использованию:

```
usage: rfmizer.py [-h] [--log-level LOG_LEVEL] config-file input-file

positional arguments:
  config-file           configuration file
  input-file            input data file

optional arguments:
  -h, --help            show this help message and exit
  --log-level LOG_LEVEL
                        logging level, defaults to WARNING
```

Примеры:

```
python rfmizer.py config.yaml orders.csv
python rfmizer.py --log=INFO config.yaml orders.csv
python rfmizer.py -h
```


## Требования к исходным данным

### Формат CSV-файла с информацией о заказах

- Файл должен быть в кодировке UTF-8.
- В начале файла НЕ должно быть маркера последовательности байтов (BOM, byte order marker).
- В качестве символа перевода строки должен использоваться символ «перевод строки»,
  он же «LF», он же «\n», он же «0x0A», он же «U+000A».
- Поля в строках должны разделяться запятыми: «,».
- В качестве символа десятичной точки в числах должен использоваться символ «.» (точка)
  или символ «,» (запятая).
- В полях, содержащих двойные кавычки «"», все символы двойных кавычек доджны быть задвоены:
  везде вместо «"» надо вставить «""»
- Поля, содержащие запятую «,», двойные кавычки «"» или переводы строки, должны быть заключены 
  двойные кавычки «"».


### Состав полей CSV-файла с информацией о заказах

Обязательные поля:

1. `order_date` — дата заказа;
2. `user_id` — уникальный обезличенный идентификатор покупателя;
3. `order_value` — cумма заказа.

Если присутствуют другие поля, то они могут расцениваться как поля, содержащие значения
дополнительных измерений, например, код географичекого расположения покупателя и т.п. Чтобы такие
поля были приняты за дополнительные измерения, их необходимо перечислить в секции `input_columns`
конфигурационного файла.


### Описание кофигурационного файла

```yaml
input_columns:
  - order_date
  - user_id
  - order_value
  - geo_code
segments_count:
  recency: 5
  frequency: 5
  monetary: 5
rfmizer:
  look_back_period: 365
  output_columns:
    user_id: ga:dimension1
    recency: ga:dimension2
    frequency: ga:dimension3
    monetary: ga:dimension4
    geo: ga:dimension5
predictor:
  prediction_period: 182
output_path: .
```

| Раздел | Параметр | Значение |
|---|---|---|
| | `input_columns` | Массив названий полей, которые надо учитывать в файле с заказами. Поля `order_date`, `user_id` и `order_value` **обязательно** должны присутствовать в файле и **обязательно** должны быть перечислены в этом параметре. |
| `segments_count` | `recency` | Количество сегментов, на которые будут поделены покупатели по измерению «Recency of last purchase». |
| `segments_count` | `frequency` | Количество сегментов, на которые будут поделены покупатели по измерению «Frequency of purchases». |
| `segments_count` | `monetary` | Количество сегментов, на которые будут поделены покупатели по измерению «Monetary life-time value». |
| `rfmizer` | `look_back_period` | Размер периода, на котором осущетсвляется сегментирование покупаталей. Указывается в днях. |
| `rfmizer` | `output_columns` | Словарь соответсвия названий измерений названиям полей в результирующем файле, содержащем соответсвие идентификаторов покупателей номерам их сегментов по каждому измерению. |
| `predictor` | `prediction_period` | Размер периода, на котором осуществляется расчет ценности каждого сегмента покупателей. Указывается в днях. |
| | `output_path` | Путь к директории, в которой сохраняются результирующие файлы. |
