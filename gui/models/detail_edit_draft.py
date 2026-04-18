"""라이브러리 상세 편집용 드래프트 — QML 바인딩."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Property, Signal


def _s(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


class DetailEditDraft(QObject):
    """jav_metadata 편집 필드 미러."""

    draftChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._product_code = ""

        self._title_ko = ""
        self._title_ja = ""
        self._title_en = ""
        self._title_zh_cn = ""
        self._title_zh_tw = ""

        self._synopsis_ko = ""
        self._synopsis_ja = ""
        self._synopsis_en = ""
        self._synopsis_zh_cn = ""
        self._synopsis_zh_tw = ""

        self._actors_ko = ""
        self._actors_ja = ""
        self._actors_romaji = ""

        self._genres_ko = ""
        self._genres_ja = ""

        self._maker_ko = ""
        self._maker_ja = ""
        self._maker_en = ""
        self._maker_zh_cn = ""
        self._maker_zh_tw = ""

        self._release_date = ""

    def load_from_row(self, row: Any) -> None:
        self._product_code = _s(getattr(row, "product_code", ""))

        self._title_ko = _s(getattr(row, "title_ko", None) or getattr(row, "title", None))
        self._title_ja = _s(getattr(row, "title_ja", None) or getattr(row, "original_title", None))
        self._title_en = _s(getattr(row, "title_en", None))
        self._title_zh_cn = _s(getattr(row, "title_zh_cn", None))
        self._title_zh_tw = _s(getattr(row, "title_zh_tw", None))

        self._synopsis_ko = _s(getattr(row, "synopsis_ko", None) or getattr(row, "synopsis", None))
        self._synopsis_ja = _s(getattr(row, "synopsis_ja", None))
        self._synopsis_en = _s(getattr(row, "synopsis_en", None))
        self._synopsis_zh_cn = _s(getattr(row, "synopsis_zh_cn", None))
        self._synopsis_zh_tw = _s(getattr(row, "synopsis_zh_tw", None))

        self._actors_ko = _s(getattr(row, "actors_ko", None) or getattr(row, "actors", None))
        self._actors_ja = _s(getattr(row, "actors_ja", None))
        self._actors_romaji = _s(getattr(row, "actors_romaji", None))

        self._genres_ko = _s(getattr(row, "genres_ko", None) or getattr(row, "genres", None))
        self._genres_ja = _s(getattr(row, "genres_ja", None))

        self._maker_ko = _s(getattr(row, "maker_ko", None) or getattr(row, "maker", None))
        self._maker_ja = _s(getattr(row, "maker_ja", None))
        self._maker_en = _s(getattr(row, "maker_en", None))
        self._maker_zh_cn = _s(getattr(row, "maker_zh_cn", None))
        self._maker_zh_tw = _s(getattr(row, "maker_zh_tw", None))

        self._release_date = _s(getattr(row, "release_date", None))
        self.draftChanged.emit()

    def apply_to_row(self, row: Any) -> None:
        """세션 내 ORM 행에 반영(commit은 호출자)."""
        row.title_ko = self._title_ko or None
        row.title_ja = self._title_ja or None
        row.title_en = self._title_en or None
        row.title_zh_cn = self._title_zh_cn or None
        row.title_zh_tw = self._title_zh_tw or None
        row.original_title = self._title_ja or None

        row.synopsis_ko = self._synopsis_ko or None
        row.synopsis_ja = self._synopsis_ja or None
        row.synopsis_en = self._synopsis_en or None
        row.synopsis_zh_cn = self._synopsis_zh_cn or None
        row.synopsis_zh_tw = self._synopsis_zh_tw or None
        row.synopsis = self._synopsis_ko or None

        row.actors_ko = self._actors_ko or None
        row.actors_ja = self._actors_ja or None
        row.actors_romaji = self._actors_romaji or None
        row.actors = self._actors_ko or None

        row.genres_ko = self._genres_ko or None
        row.genres_ja = self._genres_ja or None
        row.genres = self._genres_ko or None

        row.maker_ko = self._maker_ko or None
        row.maker_ja = self._maker_ja or None
        row.maker_en = self._maker_en or None
        row.maker_zh_cn = self._maker_zh_cn or None
        row.maker_zh_tw = self._maker_zh_tw or None
        row.maker = self._maker_ko or None

        row.title = self._title_ko or None

        row.release_date = self._release_date or None

    @Property(str, notify=draftChanged)
    def productCode(self) -> str:
        return self._product_code

    @Property(str, notify=draftChanged)
    def titleKo(self) -> str:
        return self._title_ko

    @titleKo.setter
    def titleKo(self, v: str):
        v = _s(v)
        if v != self._title_ko:
            self._title_ko = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def titleJa(self) -> str:
        return self._title_ja

    @titleJa.setter
    def titleJa(self, v: str):
        v = _s(v)
        if v != self._title_ja:
            self._title_ja = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def titleEn(self) -> str:
        return self._title_en

    @titleEn.setter
    def titleEn(self, v: str):
        v = _s(v)
        if v != self._title_en:
            self._title_en = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def titleZhCn(self) -> str:
        return self._title_zh_cn

    @titleZhCn.setter
    def titleZhCn(self, v: str):
        v = _s(v)
        if v != self._title_zh_cn:
            self._title_zh_cn = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def titleZhTw(self) -> str:
        return self._title_zh_tw

    @titleZhTw.setter
    def titleZhTw(self, v: str):
        v = _s(v)
        if v != self._title_zh_tw:
            self._title_zh_tw = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def synopsisKo(self) -> str:
        return self._synopsis_ko

    @synopsisKo.setter
    def synopsisKo(self, v: str):
        v = _s(v)
        if v != self._synopsis_ko:
            self._synopsis_ko = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def synopsisJa(self) -> str:
        return self._synopsis_ja

    @synopsisJa.setter
    def synopsisJa(self, v: str):
        v = _s(v)
        if v != self._synopsis_ja:
            self._synopsis_ja = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def synopsisEn(self) -> str:
        return self._synopsis_en

    @synopsisEn.setter
    def synopsisEn(self, v: str):
        v = _s(v)
        if v != self._synopsis_en:
            self._synopsis_en = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def synopsisZhCn(self) -> str:
        return self._synopsis_zh_cn

    @synopsisZhCn.setter
    def synopsisZhCn(self, v: str):
        v = _s(v)
        if v != self._synopsis_zh_cn:
            self._synopsis_zh_cn = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def synopsisZhTw(self) -> str:
        return self._synopsis_zh_tw

    @synopsisZhTw.setter
    def synopsisZhTw(self, v: str):
        v = _s(v)
        if v != self._synopsis_zh_tw:
            self._synopsis_zh_tw = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def actorsKo(self) -> str:
        return self._actors_ko

    @actorsKo.setter
    def actorsKo(self, v: str):
        v = _s(v)
        if v != self._actors_ko:
            self._actors_ko = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def actorsJa(self) -> str:
        return self._actors_ja

    @actorsJa.setter
    def actorsJa(self, v: str):
        v = _s(v)
        if v != self._actors_ja:
            self._actors_ja = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def actorsRomaji(self) -> str:
        return self._actors_romaji

    @actorsRomaji.setter
    def actorsRomaji(self, v: str):
        v = _s(v)
        if v != self._actors_romaji:
            self._actors_romaji = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def genresKo(self) -> str:
        return self._genres_ko

    @genresKo.setter
    def genresKo(self, v: str):
        v = _s(v)
        if v != self._genres_ko:
            self._genres_ko = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def genresJa(self) -> str:
        return self._genres_ja

    @genresJa.setter
    def genresJa(self, v: str):
        v = _s(v)
        if v != self._genres_ja:
            self._genres_ja = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def makerKo(self) -> str:
        return self._maker_ko

    @makerKo.setter
    def makerKo(self, v: str):
        v = _s(v)
        if v != self._maker_ko:
            self._maker_ko = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def makerJa(self) -> str:
        return self._maker_ja

    @makerJa.setter
    def makerJa(self, v: str):
        v = _s(v)
        if v != self._maker_ja:
            self._maker_ja = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def makerEn(self) -> str:
        return self._maker_en

    @makerEn.setter
    def makerEn(self, v: str):
        v = _s(v)
        if v != self._maker_en:
            self._maker_en = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def makerZhCn(self) -> str:
        return self._maker_zh_cn

    @makerZhCn.setter
    def makerZhCn(self, v: str):
        v = _s(v)
        if v != self._maker_zh_cn:
            self._maker_zh_cn = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def makerZhTw(self) -> str:
        return self._maker_zh_tw

    @makerZhTw.setter
    def makerZhTw(self, v: str):
        v = _s(v)
        if v != self._maker_zh_tw:
            self._maker_zh_tw = v
            self.draftChanged.emit()

    @Property(str, notify=draftChanged)
    def releaseDate(self) -> str:
        return self._release_date

    @releaseDate.setter
    def releaseDate(self, v: str):
        v = _s(v)
        if v != self._release_date:
            self._release_date = v
            self.draftChanged.emit()
