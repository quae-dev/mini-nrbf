# mini-nrbf

Bare-bones MS-NRBF serializer written in Python.

## Installation

```shell
pip install git+https://github.com/quae-dev/mini-nrbf.git
```

## Usage

```python
import mini_nrbf

records = mini_nrbf.load_file("data.bin")

for record in records:
    if isinstance(record, mini_nrbf.BinaryObjectString):
        record.value = "new value"

mini_nrbf.dump_file(records, "data.bin")
```

## License

BSD 3-Clause — see [LICENSE] for full text.

## Third-Party Licenses

This project is based off of [netfleece] by nago.

See [THIRD_PARTY_LICENSES.md] for
full text and attribution.

<!-- Links -->

[LICENSE]: https://github.com/quae-dev/mini-nrbf/blob/main/LICENSE
[netfleece]: https://gitlab.com/malie-library/netfleece.git
[THIRD_PARTY_LICENSES.md]: https://github.com/quae-dev/mini-nrbf/blob/main/THIRD_PARTY_LICENSES.md
