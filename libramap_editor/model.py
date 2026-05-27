from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


OBJECT_TYPES = ("shelf", "wall", "stairs", "elevator", "desk", "restricted", "return_box")


class MapDataError(ValueError):
    pass


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str


class ShelfMapDocument:
    def __init__(self, data: dict[str, Any], path: Path | None = None) -> None:
        self._data = data
        self.path = path
        self.validate_or_raise()

    @classmethod
    def load(cls, path: Path) -> "ShelfMapDocument":
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return cls(data=data, path=path)

    @classmethod
    def empty(cls) -> "ShelfMapDocument":
        return cls({"floors": []})

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    def save(self, path: Path | None = None) -> None:
        output_path = path or self.path
        if output_path is None:
            raise MapDataError("保存先が指定されていません。")
        self.validate_or_raise()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(self._data, file, ensure_ascii=False, indent=2)
            file.write("\n")
        self.path = output_path

    def clone_data(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)

    def floors(self) -> list[dict[str, Any]]:
        return self._data.setdefault("floors", [])

    def add_floor(self, floor_id: str, name: str) -> dict[str, Any]:
        floor_id = floor_id.strip()
        name = name.strip()
        if not floor_id:
            raise MapDataError("フロアIDを入力してください。")
        if any(floor.get("id") == floor_id for floor in self.floors()):
            raise MapDataError(f"フロアIDが重複しています: {floor_id}")
        floor = {"id": floor_id, "name": name or floor_id, "objects": []}
        self.floors().append(floor)
        return floor

    def delete_floor(self, floor_id: str) -> None:
        floors = self.floors()
        self._data["floors"] = [floor for floor in floors if floor.get("id") != floor_id]

    def floor(self, floor_id: str) -> dict[str, Any] | None:
        for floor in self.floors():
            if floor.get("id") == floor_id:
                return floor
        return None

    def objects(self, floor_id: str) -> list[dict[str, Any]]:
        floor = self.floor(floor_id)
        if floor is None:
            return []
        return floor.setdefault("objects", [])

    def add_object(self, floor_id: str, obj_type: str, obj_id: str) -> dict[str, Any]:
        if obj_type not in OBJECT_TYPES:
            raise MapDataError(f"未対応のオブジェクト種別です: {obj_type}")
        obj_id = obj_id.strip()
        if not obj_id:
            raise MapDataError("オブジェクトIDを入力してください。")
        if self.object_by_id(floor_id, obj_id) is not None:
            raise MapDataError(f"オブジェクトIDが重複しています: {obj_id}")

        obj: dict[str, Any] = {
            "type": obj_type,
            "id": obj_id,
            "x": 80,
            "y": 80,
            "width": 100,
            "height": 80,
        }
        if obj_type == "shelf":
            obj.update({"rows": 5, "cols": 8, "segments": []})
        self.objects(floor_id).append(obj)
        return obj

    def update_object(self, floor_id: str, original_id: str, values: dict[str, Any]) -> dict[str, Any]:
        obj = self.object_by_id(floor_id, original_id)
        if obj is None:
            raise MapDataError(f"オブジェクトが見つかりません: {original_id}")

        new_id = str(values.get("id", original_id)).strip()
        if not new_id:
            raise MapDataError("オブジェクトIDを入力してください。")
        existing = self.object_by_id(floor_id, new_id)
        if new_id != original_id and existing is not None:
            raise MapDataError(f"オブジェクトIDが重複しています: {new_id}")

        obj["id"] = new_id
        obj["type"] = values.get("type", obj.get("type", "shelf"))
        obj["x"] = int(values.get("x", obj.get("x", 0)))
        obj["y"] = int(values.get("y", obj.get("y", 0)))
        obj["width"] = max(1, int(values.get("width", obj.get("width", 1))))
        obj["height"] = max(1, int(values.get("height", obj.get("height", 1))))

        if obj["type"] == "shelf":
            obj["rows"] = max(1, int(values.get("rows", obj.get("rows", 5))))
            obj["cols"] = max(1, int(values.get("cols", obj.get("cols", 8))))
            obj.setdefault("segments", [])
        else:
            obj.pop("rows", None)
            obj.pop("cols", None)
            obj.pop("segments", None)
        return obj

    def delete_object(self, floor_id: str, obj_id: str) -> None:
        floor = self.floor(floor_id)
        if floor is None:
            return
        floor["objects"] = [obj for obj in floor.get("objects", []) if obj.get("id") != obj_id]

    def object_by_id(self, floor_id: str, obj_id: str) -> dict[str, Any] | None:
        for obj in self.objects(floor_id):
            if obj.get("id") == obj_id:
                return obj
        return None

    def add_segment(
        self,
        floor_id: str,
        shelf_id: str,
        row: int,
        col_start: int,
        col_end: int,
        ndc_start: str,
        ndc_end: str,
    ) -> dict[str, Any]:
        shelf = self.object_by_id(floor_id, shelf_id)
        if shelf is None or shelf.get("type") != "shelf":
            raise MapDataError("書架を選択してください。")
        segment = {
            "row": int(row),
            "col_start": int(col_start),
            "col_end": int(col_end),
            "ndc_start": ndc_start.strip(),
            "ndc_end": ndc_end.strip(),
        }
        shelf.setdefault("segments", []).append(segment)
        self.validate_or_raise()
        return segment

    def update_segment(self, floor_id: str, shelf_id: str, index: int, values: dict[str, Any]) -> None:
        shelf = self.object_by_id(floor_id, shelf_id)
        if shelf is None or shelf.get("type") != "shelf":
            raise MapDataError("書架を選択してください。")
        segments = shelf.setdefault("segments", [])
        if index < 0 or index >= len(segments):
            raise MapDataError("セグメントが見つかりません。")
        segments[index] = {
            "row": int(values["row"]),
            "col_start": int(values["col_start"]),
            "col_end": int(values["col_end"]),
            "ndc_start": str(values["ndc_start"]).strip(),
            "ndc_end": str(values["ndc_end"]).strip(),
        }
        self.validate_or_raise()

    def delete_segment(self, floor_id: str, shelf_id: str, index: int) -> None:
        shelf = self.object_by_id(floor_id, shelf_id)
        if shelf is None:
            return
        segments = shelf.setdefault("segments", [])
        if 0 <= index < len(segments):
            del segments[index]

    def validate(self) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not isinstance(self._data.get("floors"), list):
            return [ValidationIssue("floors", "floorsは配列である必要があります。")]

        floor_ids: set[str] = set()
        for floor_index, floor in enumerate(self.floors()):
            floor_path = f"floors[{floor_index}]"
            floor_id = str(floor.get("id", "")).strip()
            if not floor_id:
                issues.append(ValidationIssue(f"{floor_path}.id", "フロアIDが空です。"))
            elif floor_id in floor_ids:
                issues.append(ValidationIssue(f"{floor_path}.id", f"フロアIDが重複しています: {floor_id}"))
            floor_ids.add(floor_id)

            object_ids: set[str] = set()
            for object_index, obj in enumerate(floor.get("objects", [])):
                object_path = f"{floor_path}.objects[{object_index}]"
                obj_id = str(obj.get("id", "")).strip()
                obj_type = obj.get("type")
                if obj_type not in OBJECT_TYPES:
                    issues.append(ValidationIssue(f"{object_path}.type", f"未対応の種別です: {obj_type}"))
                if not obj_id:
                    issues.append(ValidationIssue(f"{object_path}.id", "オブジェクトIDが空です。"))
                elif obj_id in object_ids:
                    issues.append(ValidationIssue(f"{object_path}.id", f"オブジェクトIDが重複しています: {obj_id}"))
                object_ids.add(obj_id)
                for key in ("x", "y", "width", "height"):
                    if not isinstance(obj.get(key), int):
                        issues.append(ValidationIssue(f"{object_path}.{key}", f"{key}は整数である必要があります。"))
                if int(obj.get("width", 0)) <= 0 or int(obj.get("height", 0)) <= 0:
                    issues.append(ValidationIssue(object_path, "width/heightは1以上である必要があります。"))
                if obj_type == "shelf":
                    issues.extend(self._validate_shelf(obj, object_path))
        return issues

    def validate_or_raise(self) -> None:
        issues = self.validate()
        if issues:
            message = "\n".join(f"{issue.path}: {issue.message}" for issue in issues)
            raise MapDataError(message)

    @staticmethod
    def _validate_shelf(shelf: dict[str, Any], path: str) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        rows = int(shelf.get("rows", 0))
        cols = int(shelf.get("cols", 0))
        if rows <= 0 or cols <= 0:
            issues.append(ValidationIssue(path, "書架のrows/colsは1以上である必要があります。"))
        for index, segment in enumerate(shelf.get("segments", [])):
            segment_path = f"{path}.segments[{index}]"
            row = int(segment.get("row", -1))
            col_start = int(segment.get("col_start", -1))
            col_end = int(segment.get("col_end", -1))
            if row < 0 or row >= rows:
                issues.append(ValidationIssue(f"{segment_path}.row", "rowが書架範囲外です。"))
            if col_start < 0 or col_end < col_start or col_end >= cols:
                issues.append(ValidationIssue(segment_path, "列範囲が書架範囲外です。"))
            if not segment.get("ndc_start") or not segment.get("ndc_end"):
                issues.append(ValidationIssue(segment_path, "NDC範囲を入力してください。"))
        return issues
