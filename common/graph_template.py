import functools
import typing
from urllib.parse import urlencode

import orjson


@functools.lru_cache(maxsize=128)
def graph_dict(
    title: str,
    scale_label: str,
    bottom_label: str,
    labels: tuple[str, ...],
    data: tuple[int, ...],
    *,
    max_value: typing.Optional[int] = 70,
) -> dict[str, typing.Any]:
    config = {
        "type": "bar",
        "data": {
            "datasets": [
                {
                    "backgroundColor": "#a682e3",
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
                            "labelString": bottom_label,
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
                            "labelString": scale_label,
                        },
                    }
                ],
            },
        },
    }

    if not max_value:
        config["options"]["scales"]["yAxes"][0]["ticks"].pop("max", None)

    return config


@functools.lru_cache(maxsize=128)
def graph_template(
    title: str,
    scale_label: str,
    bottom_label: str,
    labels: tuple[str, ...],
    data: tuple[int, ...],
    *,
    width: int = 700,
    height: int = 400,
    max_value: typing.Optional[int] = 70,
) -> str:
    config = graph_dict(
        title, scale_label, bottom_label, labels, data, max_value=max_value
    )

    payload = {
        "bkg": "white",
        "w": width,
        "h": height,
        "chart": orjson.dumps(config),
    }

    return f"https://quickchart.io/chart?{urlencode(payload)}"


@functools.lru_cache(maxsize=128)
def multi_graph_dict(
    title: str,
    scale_label: str,
    bottom_label: str,
    labels: tuple[str, ...],
    gamertags: typing.Iterable[str],
    datas: tuple[tuple[int, ...], ...],
    *,
    max_value: typing.Optional[int] = 70,
) -> dict[str, typing.Any]:
    config = {
        "type": "bar",
        "data": {
            "datasets": [
                {"label": gamertag, "data": list(data)}
                for gamertag, data in zip(gamertags, datas, strict=True)
            ],
            "labels": list(labels),
        },
        "options": {
            "title": {
                "display": True,
                "text": title,
            },
            "legend": {
                "display": True,
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
                            "labelString": bottom_label,
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
                            "labelString": scale_label,
                        },
                    }
                ],
            },
        },
    }

    if not max_value:
        config["options"]["scales"]["yAxes"][0]["ticks"].pop("max", None)

    return config


@functools.lru_cache(maxsize=128)
def multi_graph_template(
    title: str,
    scale_label: str,
    bottom_label: str,
    labels: tuple[str, ...],
    gamertags: typing.Iterable[str],
    datas: tuple[tuple[int, ...], ...],
    *,
    width: int = 700,
    height: int = 400,
    max_value: typing.Optional[int] = 70,
) -> str:
    config = multi_graph_dict(
        title, scale_label, bottom_label, labels, gamertags, datas, max_value=max_value
    )

    payload = {
        "bkg": "white",
        "w": width,
        "h": height,
        "chart": orjson.dumps(config),
    }

    return f"https://quickchart.io/chart?{urlencode(payload)}"
