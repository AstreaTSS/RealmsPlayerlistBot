import base64
import functools
import typing
from urllib.parse import urlencode

import orjson


@functools.lru_cache(maxsize=128)
def graph_template(
    title: str,
    date_format: str,
    labels: tuple[str],
    data: tuple[int],
    *,
    width: int = 700,
    height: int = 400,
    max_value: typing.Optional[int] = 70,
) -> str:
    config = {
        "type": "bar",
        "data": {
            "datasets": [
                {
                    "backgroundColor": "#8ac249",
                    "borderColor": "#92b972",
                    "borderWidth": 0,
                    "data": list(data),
                    "type": "bar",
                }
            ],
            "labels": list(labels),
        },
        "options": {
            "title": {
                "display": True,
                "text": title,
            },
            "legend": {
                "display": False,
            },
            "scales": {
                "xAxes": [
                    {
                        "id": "X1",
                        "display": True,
                        "position": "bottom",
                        "distribution": "linear",
                        "scaleLabel": {
                            "display": True,
                            "labelString": f"Date and Hour (UTC) in {date_format}",
                        },
                    }
                ],
                "yAxes": [
                    {
                        "ticks": {
                            "display": True,
                            "fontSize": 12,
                            "min": 0,
                            "max": max_value,
                        },
                        "scaleLabel": {
                            "display": True,
                            "labelString": "Minutes Played",
                        },
                    }
                ],
            },
        },
    }

    if not max_value:
        config["options"]["scales"]["yAxes"][0]["ticks"].pop("max", None)

    payload = {
        "encoding": "base64",
        "bkg": "white",
        "w": width,
        "h": height,
        "chart": base64.urlsafe_b64encode(orjson.dumps(config)),
    }

    return f"https://quickchart.io/chart?{urlencode(payload)}"
