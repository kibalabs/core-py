from pydantic import JsonValue

JsonBaseType = str | int | float | bool | None
type Json = JsonValue
type JsonObject = dict[str, JsonValue]
type JsonList = list[JsonValue]
