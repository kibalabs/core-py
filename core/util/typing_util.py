from pydantic import JsonValue

type Json = JsonValue
type JsonObject = dict[str, JsonValue]
type JsonList = list[JsonValue]
