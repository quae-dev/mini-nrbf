# mini-nrbf

Bare-bones MS-NRBF parser written in Python.

## Installation

```shell
pip install git+https://github.com/quae-dev/mini-nrbf.git
```

## Usage

```python
import mini_nrbf

records = mini_nrbf.parse_file("data.bin")

for record in records:
    if isinstance(record, mini_nrbf.BinaryObjectString):
        record.value = "new value"

mini_nrbf.serialize_to_file(records, "data.bin")
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
