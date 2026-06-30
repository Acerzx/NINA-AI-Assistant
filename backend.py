"""
NINA AI Assistant Web
"""
import asyncio
import json
import logging
import logging.handlers
import math
import os
import re
import threading
import time
import glob
import csv
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from contextlib import asynccontextmanager
import requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel


# =====================================================================
# ПОЛНЫЙ СЛОВАРЬ МАППИНГА
# =====================================================================
TYPE_NAMES = {
    # === ОБЩИЕ КОНТЕЙНЕРЫ ===
    "SequenceRootContainer": "Последовательность",
    "StartAreaContainer": "Начало",
    "TargetAreaContainer": "Цели",
    "EndAreaContainer": "Конец",
    "SequentialContainer": "Последовательный блок",
    "ParallelContainer": "Параллельный блок",
    "DeepSkyObjectContainer": "DSO объект",
    # === ПОДКЛЮЧЕНИЕ/ОТКЛЮЧЕНИЕ ===
    "ConnectEquipment": "Подключить оборудование",
    "DisconnectAllEquipment": "Отключить всё оборудование",
    "ReconnectTrigger": "Переподключить оборудование",
    "ReconnectOnDownloadFailure": "Переподключить камеру при ошибке загрузки",
    # === КАМЕРА ===
    "CoolCamera": "Охлаждение камеры",
    "WarmCamera": "Прогрев камеры",
    "TakeExposure": "Съёмка кадра",
    "SmartExposure": "Умная экспозиция",
    # === МОНТИРОВКА ===
    "UnparkScope": "Распарковать телескоп",
    "ParkScope": "Запарковать телескоп",
    "SlewScope": "Наведение телескопа",
    "SlewScopeToAltAz": "Движение к Альт/Аз",
    "SetTracking": "Задать слежение",
    "HomeMount": "Домой",
    # === ФОКУСЁР ===
    "MoveFocuserAbsolute": "Переместить фокусёр",
    "RunAutofocus": "Запустить автофокус",
    # === ФИЛЬТРЫ ===
    "SwitchFilter": "Сменить фильтр",
    # === ГИД ===
    "StartGuiding": "Начать гидирование",
    "StopGuiding": "Остановить гидирование",
    "Dither": "Дизеринг",
    # === PLATESOLVE ===
    "SolveAndSync": "Разрешить и синхронизировать",
    "CenterAndRotate": "Двигаться, отцентрировать и вращать",
    # === УТИЛИТЫ ===
    "Annotation": "Аннотация",
    "MessageBox": "Окно сообщения",
    "WaitForTimeSpan": "Время ожидания",
    "WaitForTime": "Ожидание времени",
    "WaitForAltitude": "Дождаться высоты",
    "GlobalVariable": "Определить переменную",
    # === ПЛАГИНЫ ===
    "NightSummaryInstruction": "Night Summary Start",
    "NightSummaryEndInstruction": "Night Summary End",
    "TwoPointPolarAlignmentSequenceItem": "2-Point Polar Alignment",
    "StartLivestacking": "Start live stacking",
    "StopLivestacking": "Stop live stacking",
    "Phd2SettleInstruction": "PHD2 Wait for Settle",
    "Phd2SettleTrigger": "PHD2 Settle Trigger",
    "ShutdownPhd2Instruction": "Shutdown PHD2",
    "ShutdownNina": "Shutdown N.I.N.A.",
    "ShutdownPcInstruction": "Shutdown PC",
    "InjectAutofocusTrigger": "Inject Autofocus",
    "InjectAutofocusTrigger_Test": "Inject Autofocus (Test)",
    "FlexureCompensatorTrigger": "Flexure Compensator",
    "RestartWhenSaturated": "Restart When Saturated",
    "InterruptWhenRMSAbove": "Interrupt when RMS above",
    # === ТРИГГЕРЫ ===
    "DitherAfterExposures": "Дизеринг после экспозиций",
    "MeridianFlipTrigger": "Перекладка меридиана",
    "RestoreGuiding": "Возобновить гидирование",
    "CenterAfterDriftTrigger": "Центр после дрейфа",
    "AutofocusAfterFilterChange": "АФ после изменения фильтра",
    "AutofocusAfterHFRIncreaseTrigger": "АФ после увеличения HFR",
    "AutofocusAfterTemperatureChangeTrigger": "АФ после изменения температуры",
    "AutofocusAfterTimeTrigger": "АФ после времени",
    "ReconnectCameraOnDownloadFailure": "Reconnect Camera On Download Failure",
    # === УСЛОВИЯ ===
    "AboveHorizonCondition": "Выше горизонта",
    "TimeCondition": "Осталось",
    "LoopCondition": "Цикл",
}

DEVICE_NAMES = {
    "Camera": "Камера",
    "Filter Wheel": "Фильтры",
    "Focuser": "Фокусёр",
    "Rotator": "Ротатор",
    "Mount": "Монтировка",
    "Guider": "Гид",
    "Weather": "Погода",
}

TRACKING_MODES = {0: "Sidereal", 1: "Lunar", 2: "Solar", 3: "King", 5: "Stop"}
TRACKING_MODES_RU = {0: "Звёздная", 1: "Лунная", 2: "Солнечная", 3: "King", 5: "Стоп"}
IMAGE_TYPES = {"LIGHT": "Light", "FLAT": "Flat", "DARK": "Dark", "BIAS": "Bias"}
ERROR_BEHAVIORS = {0: "Stop", 1: "Continue", 2: "Repeat", 3: "Abort"}
ERROR_BEHAVIORS_RU = {0: "Остановить", 1: "Продолжить", 2: "Повторить", 3: "Прервать"}
POLAR_ALIGN_METHODS = {0: "2-Point", 1: "1-Point"}


def sanitize_for_json(obj):
    """Рекурсивная очистка объекта для сериализации в JSON (NaN/Inf -> None)"""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj


def setup_logging():
    """Настройка логирования с ротацией файлов и консольным выводом"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger = logging.getLogger("NinaAI")
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "nina_ai.log", maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


logger = setup_logging()


class CommandRequest(BaseModel):
    action: str
    params: Dict[str, Any] = {}


class SettingsRequest(BaseModel):
    settings: Dict[str, Any]


class ChatMessage(BaseModel):
    message: str


# =====================================================================
# PROMETHEUS-STYLE METRICS COLLECTOR (из nina-prometheus-exporter)
# =====================================================================
class PrometheusMetrics:
    """
    Сборщик метрик в стиле Prometheus.
    Собирает данные из backend и экспортирует их в формате Prometheus text exposition.
    Также хранит историю для построения графиков в UI.
    """

    def __init__(self, backend_ref):
        self.backend = backend_ref
        self.metrics: Dict[str, Dict[str, Any]] = {}
        self.history: List[Dict[str, Any]] = []
        self.max_history = 5000
        self.lock = threading.Lock()
        self._init_metrics()

    def _init_metrics(self):
        """Инициализация всех метрик в формате Prometheus"""
        # Оборудование
        self._define("nina_equipment_connected", "gauge", "Equipment connection status (0/1)", ["device"])
        
        # Камера
        self._define("nina_camera_temperature_celsius", "gauge", "Camera sensor temperature in Celsius")
        self._define("nina_camera_target_temperature_celsius", "gauge", "Camera target temperature in Celsius")
        self._define("nina_camera_cooler_power_percent", "gauge", "Camera cooler power percentage (0-100)")
        self._define("nina_camera_is_exposing", "gauge", "Camera exposing flag (0/1)")
        self._define("nina_camera_gain", "gauge", "Camera gain value")
        self._define("nina_camera_offset", "gauge", "Camera offset value")
        
        # Последовательность
        self._define("nina_sequence_state", "gauge", "Sequence state (0=stopped, 1=running, 2=paused)")
        
        # Изображения
        self._define("nina_image_hfr_pixels", "gauge", "Last image Half-Flux-Radius in pixels")
        self._define("nina_image_fwhm_pixels", "gauge", "Last image FWHM in pixels")
        self._define("nina_image_stars_count", "gauge", "Number of stars detected in last image")
        self._define("nina_image_mean_brightness", "gauge", "Mean brightness of last image")
        self._define("nina_image_exposure_seconds", "gauge", "Last image exposure time in seconds")
        
        # Гид
        self._define("nina_guider_is_guiding", "gauge", "Guiding active flag (0/1)")
        self._define("nina_guider_rms_total_arcsec", "gauge", "Guider RMS Total in arcseconds")
        self._define("nina_guider_rms_ra_arcsec", "gauge", "Guider RMS RA in arcseconds")
        self._define("nina_guider_rms_dec_arcsec", "gauge", "Guider RMS Dec in arcseconds")
        
        # Монтировка
        self._define("nina_mount_ra_hours", "gauge", "Mount Right Ascension in hours")
        self._define("nina_mount_dec_degrees", "gauge", "Mount Declination in degrees")
        self._define("nina_mount_tracking", "gauge", "Mount tracking flag (0/1)")
        self._define("nina_mount_slewing", "gauge", "Mount slewing flag (0/1)")
        self._define("nina_mount_parked", "gauge", "Mount parked flag (0/1)")
        
        # Фокусёр
        self._define("nina_focuser_position_steps", "gauge", "Focuser position in steps")
        self._define("nina_focuser_temperature_celsius", "gauge", "Focuser ambient temperature in Celsius")
        self._define("nina_focuser_moving", "gauge", "Focuser moving flag (0/1)")
        
        # Фильтры
        self._define("nina_filter_current_id", "gauge", "Current filter ID")
        
        # Ротатор
        self._define("nina_rotator_position_degrees", "gauge", "Rotator position in degrees")
        
        # Окружающая среда
        self._define("nina_environment_temperature_celsius", "gauge", "Environment temperature in Celsius")
        self._define("nina_environment_humidity_percent", "gauge", "Environment humidity percentage")
        self._define("nina_environment_pressure_hpa", "gauge", "Environment pressure in hPa")
        self._define("nina_environment_cloud_cover_percent", "gauge", "Cloud cover percentage")
        self._define("nina_environment_wind_speed_ms", "gauge", "Wind speed in m/s")
        self._define("nina_environment_safe", "gauge", "Environment safe flag (0/1)")
        
        # Сессия
        self._define("nina_session_frames_total", "counter", "Total number of frames captured in session")
        self._define("nina_session_exposure_seconds_total", "counter", "Total exposure time in session (seconds)")
        
        # API статистика
        self._define("nina_api_requests_total", "counter", "Total NINA API requests", ["endpoint"])
        self._define("nina_api_errors_total", "counter", "Total NINA API errors", ["endpoint"])
        
        # AI статистика
        self._define("nina_ai_requests_total", "counter", "Total AI requests")
        self._define("nina_ai_errors_total", "counter", "Total AI errors")

    def _define(self, name: str, mtype: str, help_text: str, labels: List[str] = None):
        """Определение новой метрики"""
        self.metrics[name] = {
            "type": mtype,
            "help": help_text,
            "labels": labels or [],
            "values": {},
            "last_update": None,
        }

    def set(self, name: str, value, labels: Dict[str, str] = None):
        """Установка значения метрики"""
        with self.lock:
            if name not in self.metrics:
                return
            if value is None:
                return
            try:
                v = float(value)
            except (TypeError, ValueError):
                return
            if math.isnan(v) or math.isinf(v):
                return
            key = self._label_key(labels)
            self.metrics[name]["values"][key] = {
                "value": v,
                "labels": labels or {},
                "timestamp": time.time(),
            }
            self.metrics[name]["last_update"] = time.time()

    def inc(self, name: str, amount: float = 1.0, labels: Dict[str, str] = None):
        """Инкремент счётчика"""
        with self.lock:
            if name not in self.metrics:
                return
            key = self._label_key(labels)
            current = self.metrics[name]["values"].get(key, {}).get("value", 0.0)
            self.metrics[name]["values"][key] = {
                "value": current + amount,
                "labels": labels or {},
                "timestamp": time.time(),
            }
            self.metrics[name]["last_update"] = time.time()

    def _label_key(self, labels: Dict[str, str] = None) -> str:
        """Генерация ключа из labels"""
        if not labels:
            return ""
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))

    def export_prometheus(self) -> str:
        """Экспорт в формате Prometheus text exposition format"""
        lines = []
        with self.lock:
            for name, metric in self.metrics.items():
                if not metric["values"]:
                    continue
                lines.append(f"# HELP {name} {metric['help']}")
                lines.append(f"# TYPE {name} {metric['type']}")
                for key, data in metric["values"].items():
                    if data["labels"]:
                        label_str = ",".join(f'{k}="{v}"' for k, v in data["labels"].items())
                        lines.append(f"{name}{{{label_str}}} {data['value']}")
                    else:
                        lines.append(f"{name} {data['value']}")
        return "\n".join(lines) + "\n"

    def snapshot(self) -> Dict[str, Any]:
        """Снимок всех метрик для UI (JSON формат)"""
        snapshot = {}
        with self.lock:
            for name, metric in self.metrics.items():
                if not metric["values"]:
                    continue
                if metric["labels"]:
                    snapshot[name] = {
                        k: v["value"] for k, v in metric["values"].items()
                    }
                else:
                    first = next(iter(metric["values"].values()), None)
                    snapshot[name] = first["value"] if first else None
        return snapshot

    def record_history(self):
        """Записать текущий снимок в историю для графиков"""
        snapshot = self.snapshot()
        if not snapshot:
            return
        entry = {"timestamp": datetime.now().isoformat(), **snapshot}
        with self.lock:
            self.history.append(entry)
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]

    def get_history(self, minutes: int = 60) -> List[Dict[str, Any]]:
        """Получить историю за последние N минут"""
        cutoff = (datetime.now() - timedelta(minutes=minutes)).isoformat()
        with self.lock:
            return [h for h in self.history if h.get("timestamp", "") >= cutoff]

    def collect_from_backend(self):
        """Собрать метрики из текущего состояния backend"""
        b = self.backend
        
        # Статус оборудования
        for dev in ["Camera", "Mount", "Focuser", "FilterWheel", "Guider", "Rotator", "Weather"]:
            dev_data = b.equipment_registry.get(dev, {})
            self.set("nina_equipment_connected", 
                     1 if dev_data.get("Connected") else 0, 
                     {"device": dev})

        # Камера
        cam = b.detailed_telemetry.get("camera", {})
        if cam:
            self.set("nina_camera_temperature_celsius", cam.get("temperature"))
            self.set("nina_camera_target_temperature_celsius", cam.get("target_temp"))
            cp = cam.get("cooler_power")
            if cp is not None:
                self.set("nina_camera_cooler_power_percent", float(cp) * 100)
            self.set("nina_camera_is_exposing", 1 if cam.get("is_exposing") else 0)
            self.set("nina_camera_gain", cam.get("gain"))
            self.set("nina_camera_offset", cam.get("offset"))

        # Монтировка
        mnt = b.detailed_telemetry.get("mount", {})
        if mnt:
            self.set("nina_mount_ra_hours", mnt.get("right_ascension"))
            self.set("nina_mount_dec_degrees", mnt.get("declination"))
            self.set("nina_mount_tracking", 1 if mnt.get("tracking") else 0)
            self.set("nina_mount_slewing", 1 if mnt.get("slewing") else 0)
            self.set("nina_mount_parked", 1 if mnt.get("parked") else 0)

        # Фокусёр
        foc = b.detailed_telemetry.get("focuser", {})
        if foc:
            self.set("nina_focuser_position_steps", foc.get("position"))
            self.set("nina_focuser_temperature_celsius", foc.get("temperature"))
            self.set("nina_focuser_moving", 1 if foc.get("moving") else 0)

        # Фильтры
        flt = b.detailed_telemetry.get("filters", {})
        if flt and flt.get("selected_filter"):
            sel = flt["selected_filter"]
            if isinstance(sel, dict):
                self.set("nina_filter_current_id", sel.get("Id"))
            elif isinstance(sel, str):
                fmap = b.equipment_registry.get("FilterMap", {})
                if sel in fmap:
                    self.set("nina_filter_current_id", fmap[sel])

        # Ротатор
        rot = b.detailed_telemetry.get("rotator", {})
        if rot:
            self.set("nina_rotator_position_degrees", rot.get("position"))

        # Гид
        g = b.guider_details or {}
        self.set("nina_guider_is_guiding", 1 if g.get("is_guiding") else 0)
        if g.get("unit") == "arcsec":
            self.set("nina_guider_rms_total_arcsec", g.get("rms_total"))
            self.set("nina_guider_rms_ra_arcsec", g.get("rms_ra"))
            self.set("nina_guider_rms_dec_arcsec", g.get("rms_dec"))

        # Изображения
        img = b.image_stats or {}
        self.set("nina_image_hfr_pixels", img.get("hfr"))
        self.set("nina_image_fwhm_pixels", img.get("fwhm"))
        self.set("nina_image_stars_count", img.get("stars"))
        self.set("nina_image_mean_brightness", img.get("mean"))
        self.set("nina_image_exposure_seconds", img.get("exposure"))

        # Сессия
        ss = b.session_stats or {}
        self.set("nina_session_frames_total", ss.get("total_frames"))
        self.set("nina_session_exposure_seconds_total", ss.get("total_exposure_time"))

        # Окружающая среда
        env = b.environment_data or {}
        self.set("nina_environment_temperature_celsius", env.get("temperature"))
        self.set("nina_environment_humidity_percent", env.get("humidity"))
        self.set("nina_environment_pressure_hpa", env.get("pressure"))
        self.set("nina_environment_cloud_cover_percent", env.get("cloud_cover"))
        self.set("nina_environment_wind_speed_ms", env.get("wind_speed"))
        self.set("nina_environment_safe", 1 if env.get("safe") else 0)

        # Статистика AI
        self.set("nina_ai_requests_total", b.ai_requests_count)
        self.set("nina_ai_errors_total", b.ai_errors_count)


# =====================================================================
# SESSION METADATA PARSER (из nina.plugin.sessionmetadata)
# =====================================================================
class SessionMetadataParser:
    """
    Парсит метаданные сессии в стиле tcpalmer/nina.plugin.sessionmetadata.
    Читает JSON/CSV файлы AcquisitionDetails и ImageMetaData из папки сессии.
    """

    def __init__(self, backend_ref):
        self.backend = backend_ref
        self.acquisition_details: Dict[str, Any] = {}
        self.image_metadata: List[Dict[str, Any]] = []
        self.weather_data: List[Dict[str, Any]] = []
        self.current_session_dir: Optional[str] = None
        self.last_mtime_acq = 0
        self.last_mtime_img = 0
        self.last_mtime_weather = 0

    def detect_session_dir(self) -> Optional[str]:
        """Определить текущую папку сессии по наличию файлов метаданных"""
        base = self.backend.settings.get("session_metadata_dir") or \
               self.backend.nina_profile.get("image_settings", {}).get("file_path", "")
        if not base or not os.path.exists(base):
            return None
        try:
            candidates = []
            for root, dirs, files in os.walk(base):
                if "AcquisitionDetails.json" in files or "AcquisitionDetails.csv" in files:
                    candidates.append(root)
                # Ограничение по глубине для производительности
                if root.count(os.sep) - base.count(os.sep) > 4:
                    dirs.clear()
            if not candidates:
                return None
            # Самая свежая по mtime
            return max(candidates, key=lambda p: os.path.getmtime(p))
        except Exception:
            return None

    def parse_all(self, force: bool = False):
        """Парсит все метаданные текущей сессии"""
        session_dir = self.detect_session_dir()
        if not session_dir:
            return
        if session_dir != self.current_session_dir:
            self.current_session_dir = session_dir
            self.acquisition_details = {}
            self.image_metadata = []
            self.weather_data = []
            force = True

        self._parse_acquisition(session_dir, force)
        self._parse_image_metadata(session_dir, force)
        self._parse_weather(session_dir, force)

    def _parse_acquisition(self, session_dir: str, force: bool):
        """Парсинг AcquisitionDetails.json/.csv"""
        json_path = os.path.join(session_dir, "AcquisitionDetails.json")
        csv_path = os.path.join(session_dir, "AcquisitionDetails.csv")
        target = json_path if os.path.exists(json_path) else csv_path if os.path.exists(csv_path) else None
        if not target:
            return
        mtime = os.path.getmtime(target)
        if not force and mtime <= self.last_mtime_acq:
            return
        self.last_mtime_acq = mtime
        try:
            if target.endswith(".json"):
                with open(target, "r", encoding="utf-8") as f:
                    self.acquisition_details = json.load(f)
            else:
                with open(target, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    if rows:
                        self.acquisition_details = rows[0]
        except Exception as e:
            logger.error(f"AcquisitionDetails parse error: {e}")

    def _parse_image_metadata(self, session_dir: str, force: bool):
        """Парсинг ImageMetaData.json/.csv"""
        json_path = os.path.join(session_dir, "ImageMetaData.json")
        csv_path = os.path.join(session_dir, "ImageMetaData.csv")
        target = json_path if os.path.exists(json_path) else csv_path if os.path.exists(csv_path) else None
        if not target:
            return
        mtime = os.path.getmtime(target)
        if not force and mtime <= self.last_mtime_img:
            return
        self.last_mtime_img = mtime
        try:
            if target.endswith(".json"):
                with open(target, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.image_metadata = data
                    elif isinstance(data, dict):
                        self.image_metadata = data.get("images", data.get("frames", [data]))
            else:
                with open(target, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    self.image_metadata = list(reader)
            # Нормализация числовых полей
            for row in self.image_metadata:
                for k in ["ExposureTime", "HFR", "FWHM", "StarCount", "Mean", "Median",
                          "Temperature", "GuidingRMS", "GuidingRMSRA", "GuidingRMSDec",
                          "Gain", "Offset"]:
                    if k in row and row[k] not in (None, ""):
                        try:
                            row[k] = float(row[k])
                        except (ValueError, TypeError):
                            pass
        except Exception as e:
            logger.error(f"ImageMetaData parse error: {e}")

    def _parse_weather(self, session_dir: str, force: bool):
        """Парсинг WeatherData.json/.csv"""
        json_path = os.path.join(session_dir, "WeatherData.json")
        csv_path = os.path.join(session_dir, "WeatherData.csv")
        target = json_path if os.path.exists(json_path) else csv_path if os.path.exists(csv_path) else None
        if not target:
            return
        mtime = os.path.getmtime(target)
        if not force and mtime <= self.last_mtime_weather:
            return
        self.last_mtime_weather = mtime
        try:
            if target.endswith(".json"):
                with open(target, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.weather_data = data if isinstance(data, list) else []
            else:
                with open(target, "r", encoding="utf-8") as f:
                    self.weather_data = list(csv.DictReader(f))
        except Exception:
            pass

    def get_session_summary(self) -> Dict[str, Any]:
        """Сводка по сессии с агрегированной статистикой"""
        images = self.image_metadata
        if not images:
            return {
                "session_dir": self.current_session_dir,
                "acquisition": self.acquisition_details,
                "total_frames": 0,
                "total_exposure": 0,
                "by_filter": {},
                "hfr_stats": {},
                "fwhm_stats": {},
                "images": [],
                "image_count_total": 0,
            }

        total_exp = sum(float(i.get("ExposureTime", 0) or 0) for i in images)
        by_filter: Dict[str, Any] = {}
        for img in images:
            f = img.get("Filter") or img.get("FilterName") or "Unknown"
            if f not in by_filter:
                by_filter[f] = {"count": 0, "exposure": 0, "hfr": [], "fwhm": [], "stars": []}
            by_filter[f]["count"] += 1
            by_filter[f]["exposure"] += float(img.get("ExposureTime", 0) or 0)
            for k, src in [("hfr", "HFR"), ("fwhm", "FWHM"), ("stars", "StarCount")]:
                v = img.get(src)
                if v is not None:
                    try:
                        by_filter[f][k].append(float(v))
                    except (ValueError, TypeError):
                        pass

        def stats(arr):
            """Расчёт статистики по массиву"""
            if not arr:
                return {"min": None, "max": None, "avg": None, "median": None}
            arr_s = sorted(arr)
            return {
                "min": round(min(arr), 3),
                "max": round(max(arr), 3),
                "avg": round(sum(arr) / len(arr), 3),
                "median": round(arr_s[len(arr_s) // 2], 3),
            }

        all_hfr = [float(i.get("HFR")) for i in images if i.get("HFR") is not None]
        all_fwhm = [float(i.get("FWHM")) for i in images if i.get("FWHM") is not None]

        return {
            "session_dir": self.current_session_dir,
            "acquisition": self.acquisition_details,
            "total_frames": len(images),
            "total_exposure": round(total_exp, 2),
            "total_exposure_formatted": self._format_duration(total_exp),
            "by_filter": {
                f: {
                    "count": d["count"],
                    "exposure": round(d["exposure"], 2),
                    "hfr": stats(d["hfr"]),
                    "fwhm": stats(d["fwhm"]),
                    "stars": stats(d["stars"]),
                } for f, d in by_filter.items()
            },
            "hfr_stats": stats(all_hfr),
            "fwhm_stats": stats(all_fwhm),
            "images": images[-200:],  # последние 200 кадров
            "image_count_total": len(images),
        }

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Форматирование длительности в человекочитаемый вид"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h}ч {m}м {s}с"
        if m > 0:
            return f"{m}м {s}с"
        return f"{s}с"


# =====================================================================
# CONNECTION MANAGER (WebSocket broadcasts)
# =====================================================================
class ConnectionManager:
    """Менеджер WebSocket соединений с очередью сообщений для broadcast"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.message_queue: asyncio.Queue = asyncio.Queue()

    async def start_broadcast_loop(self):
        """Запуск цикла broadcast'а сообщений всем подключённым клиентам"""
        async def broadcast_loop():
            while True:
                try:
                    message = await self.message_queue.get()
                    message = sanitize_for_json(message)
                    for connection in self.active_connections[:]:
                        try:
                            await connection.send_json(message)
                        except Exception:
                            if connection in self.active_connections:
                                self.active_connections.remove(connection)
                    self.message_queue.task_done()
                except Exception as e:
                    logger.error(f"WS Broadcast Error: {e}")
                await asyncio.sleep(0.05)
        asyncio.create_task(broadcast_loop())

    def enqueue(self, message: dict):
        """Добавить сообщение в очередь для broadcast"""
        try:
            self.message_queue.put_nowait(message)
        except Exception as e:
            logger.error(f"WS Queue Error: {e}")

    async def connect(self, websocket: WebSocket):
        """Принять новое WebSocket соединение"""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Удалить WebSocket соединение"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)


# =====================================================================
# MAIN BACKEND CLASS
# =====================================================================
class NinaBackend:
    """Главный класс backend, содержащий всю логику работы с NINA и AI"""
    
    SETTINGS_FILE = "nina_ai_settings.json"
    DSO_CATALOG_FILE = "dso_catalog.json"
    DEFAULT_PROFILES_DIR = r"C:\Users\istep\AppData\Local\NINA\Profiles"
    DEFAULT_NINA_ROOT = r"C:\Users\istep\AppData\Local\NINA"
    DEFAULT_SEQUENCE_DIR = r"C:\Users\istep\YandexDisk\Хобби\Астрономия\ПО\N.I.N.A\Set templates"
    DEFAULT_SESSION_DIR = r"C:\Users\istep\YandexDisk\Хобби\Астрономия\Фото\Сессии"

    def __init__(self, broadcast_callback: Optional[Callable] = None):
        self.is_running = True
        self.broadcast_callback = broadcast_callback
        self.settings: Dict[str, Any] = {}
        self.nina_host = "localhost"
        self.nina_port = 1888
        self.ollama_url = "http://localhost:11434"
        self.model = "gemma4:e2b"
        self.load_settings()

        self.max_chat_history = self.settings.get("chat_context_length", 10)
        self.chat_history: List[Dict[str, Any]] = []
        self.log_history: List[Dict[str, Any]] = []
        self.equipment_registry: Dict[str, Any] = {}
        self.available_models: List[str] = []
        self.dso_catalog: Dict[str, Any] = {}
        self.dso_aliases: Dict[str, str] = {}
        self.ai_mode = "auto"
        self.is_ai_thinking = False
        self.last_ai_response_time: Optional[datetime] = None
        self.ai_requests_count = 0
        self.ai_errors_count = 0
        self.ai_success_count = 0
        self.current_ai_start_time: Optional[float] = None
        self.nina_connected = False
        self.ollama_connected = False
        self.ollama_error_count = 0
        self.nina_error_count = 0
        self.OLLAMA_ERROR_THRESHOLD = 3
        self.NINA_ERROR_THRESHOLD = 3

        self.nina_profile: Dict[str, Any] = {}
        self.profile_path: str = ""
        self.profiles_dir: str = self.settings.get("profiles_dir", self.DEFAULT_PROFILES_DIR)
        self.nina_root: str = self.settings.get("nina_root", self.DEFAULT_NINA_ROOT)
        self.sequence_dir: str = self.settings.get("sequence_dir", self.DEFAULT_SEQUENCE_DIR)
        self.session_metadata_dir: str = self.settings.get("session_metadata_dir", self.DEFAULT_SESSION_DIR)

        self.image_stats: Dict[str, Any] = {}
        self.guider_details: Dict[str, Any] = {}
        self.environment_data: Dict[str, Any] = {}
        self.focuser_ambient_temp: Optional[float] = None
        self.sequence_details: Dict[str, Any] = {}
        self.sequence_tree: List[Dict] = []
        self.detailed_telemetry: Dict[str, Any] = {}
        self.image_history: List[Dict[str, Any]] = []
        self.test_results: List[Dict] = []

        self.guider_unit = self.settings.get("guider_unit", "arcsec")

        # Защита от спама логов
        self._last_sequence_source = None
        self._last_profile_log = None
        self._last_sequence_state_key = None

        self.session_stats: Dict[str, Any] = {
            "total_frames": 0, "total_exposure_time": 0.0,
            "avg_hfr": 0.0, "avg_fwhm": 0.0, "avg_stars": 0.0,
            "best_hfr": None, "worst_hfr": None,
            "current_hfr": None, "current_fwhm": None, "current_stars": None,
        }

        # Регулярные выражения для парсинга команд
        self.re_snap = re.compile(r'(?:сделай\s+)?(?:снимок|кадр|экспозиция)\s+(?:на\s+)?(\d+)\s*[ссек]?', re.IGNORECASE)
        self.re_series = re.compile(r'серия\s*[xх×]\s*(\d+)', re.IGNORECASE)
        self.re_cool = re.compile(r'охлад[иіть]?\s+(?:до\s+)?(-?\d+)', re.IGNORECASE)
        self.question_patterns = [
            r'\?', r'^что\b', r'^как\b', r'^почему\b', r'^зачем\b',
            r'^когда\b', r'^где\b', r'^сколько\b', r'^можно\b',
            r'объясни', r'расскажи', r'подскажи', r'помоги',
            r'что это', r'как это', r'почему это',
            r'какая погода', r'какое состояние', r'что происходит',
            r'как\s+дела', r'отчёт', r'статус', r'анализ', r'качество', r'диагностика', r'проблем'
        ]

        # Новые компоненты (Prometheus + Session Metadata)
        self.prometheus = PrometheusMetrics(self)
        self.session_metadata = SessionMetadataParser(self)

        self._load_dso_catalog()
        self.load_nina_profile()
        self._start_background_tasks()

    def _start_background_tasks(self):
        """Запуск всех фоновых потоков мониторинга"""
        threading.Thread(target=self._check_connections_thread, daemon=True).start()
        threading.Thread(target=self._monitor_equipment_thread, daemon=True).start()
        threading.Thread(target=self._monitor_session_thread, daemon=True).start()
        threading.Thread(target=self._monitor_profile_thread, daemon=True).start()
        threading.Thread(target=self._monitor_sequence_thread, daemon=True).start()
        threading.Thread(target=self._monitor_metrics_thread, daemon=True).start()
        threading.Thread(target=self._monitor_session_metadata_thread, daemon=True).start()

    def load_settings(self):
        """Загрузка настроек из JSON файла"""
        if os.path.exists(self.SETTINGS_FILE):
            try:
                with open(self.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        raise ValueError("Empty file")
                    self.settings = json.loads(content)
                    self.nina_host = self.settings.get("host", self.nina_host)
                    self.nina_port = self.settings.get("port", self.nina_port)
                    self.ollama_url = self.settings.get("ollama", self.ollama_url)
                    self.model = self.settings.get("model", self.model)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Файл настроек повреждён: {e}")
                self.settings = {}
            except Exception as e:
                logger.error(f"Ошибка загрузки настроек: {e}")
                self.settings = {}
        if "modules" not in self.settings:
            self.settings["modules"] = {}
        defaults = {
            "sequence": True, "camera": True, "mount": True, "focuser": True,
            "filters": True, "guider": True, "rotator": False,
            "profile": True, "telemetry": True, "weather": True, "stats": True,
            "prometheus": True, "session_metadata": True
        }
        for key, val in defaults.items():
            if key not in self.settings["modules"]:
                self.settings["modules"][key] = val
        self.settings.setdefault("chat_context_length", 10)
        self.settings.setdefault("profiles_dir", self.DEFAULT_PROFILES_DIR)
        self.settings.setdefault("nina_root", self.DEFAULT_NINA_ROOT)
        self.settings.setdefault("sequence_dir", self.DEFAULT_SEQUENCE_DIR)
        self.settings.setdefault("session_metadata_dir", self.DEFAULT_SESSION_DIR)
        self.settings.setdefault("guider_unit", "arcsec")
        self.settings.setdefault("guider_pixel_scale", 1.0)
        self.settings.setdefault("coord_units", "degrees")
        self.settings.setdefault("log_level", "INFO")
        self.settings.setdefault("prometheus", {"enabled": True, "retention_hours": 24,
                                                  "scrape_interval_seconds": 5, "history_max_points": 5000})
        self.settings.setdefault("session_metadata", {"enabled": True, "auto_detect": True,
                                                       "scan_interval_seconds": 10})

    def save_settings(self):
        """Сохранение настроек в JSON файл"""
        self.settings["host"] = self.nina_host
        self.settings["port"] = self.nina_port
        self.settings["ollama"] = self.ollama_url
        self.settings["model"] = self.model
        self.settings["profiles_dir"] = self.profiles_dir
        self.settings["nina_root"] = self.nina_root
        self.settings["sequence_dir"] = self.sequence_dir
        self.settings["session_metadata_dir"] = self.session_metadata_dir
        self.settings["guider_unit"] = self.guider_unit
        try:
            with open(self.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")

    def _load_dso_catalog(self):
        """Загрузка каталога DSO объектов"""
        if os.path.exists(self.DSO_CATALOG_FILE):
            try:
                with open(self.DSO_CATALOG_FILE, 'r', encoding='utf-8') as f:
                    self.dso_catalog = json.load(f)
                for key, data in self.dso_catalog.items():
                    self.dso_aliases[key.lower()] = key
                    for alias in data.get("aliases", []):
                        self.dso_aliases[str(alias).lower()] = key
                logger.info(f"DSO: {len(self.dso_catalog)} объектов, {len(self.dso_aliases)} алиасов")
            except Exception as e:
                logger.error(f"DSO error: {e}")
        else:
            logger.warning(f"Файл {self.DSO_CATALOG_FILE} не найден")

    # ===================================================================
    # ПОЛНЫЙ ПАРСИНГ XML ПРОФИЛЯ NINA (из v8, без сокращений)
    # ===================================================================
    def load_nina_profile(self, force_path: Optional[str] = None):
        """Загрузка и парсинг XML профиля NINA"""
        profile_file = None
        if force_path and os.path.exists(force_path):
            profile_file = force_path
        else:
            try:
                if os.path.exists(self.profiles_dir):
                    profiles = glob.glob(os.path.join(self.profiles_dir, "*.profile"))
                    if profiles:
                        profile_file = max(profiles, key=os.path.getmtime)
            except Exception as e:
                self.log(f"Ошибка поиска профиля: {e}", "WARNING")
        if not profile_file or not os.path.exists(profile_file):
            self.log("Файл профиля не найден", "WARNING")
            return
        self.profile_path = profile_file
        profile_data = {
            "file_path": profile_file,
            "file_name": os.path.basename(profile_file),
            "loaded_at": datetime.now().isoformat(),
        }
        try:
            tree = ET.parse(profile_file)
            root = tree.getroot()

            def find_direct_text(parent, tag, default=None):
                """Ищет тег ТОЛЬКО среди прямых потомков элемента"""
                if parent is None: return default
                for child in parent:
                    child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    if child_tag == tag and child.text and child.text.strip():
                        return child.text.strip()
                return default

            def find_section(parent, section_name):
                """Ищет секцию среди прямых потомков"""
                if parent is None: return None
                for child in parent:
                    child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    if child_tag == section_name:
                        return child
                return None

            def find_text(parent, tag, default=None):
                """Рекурсивный поиск текста с игнорированием namespace"""
                if parent is None: return default
                try:
                    el = parent.find(f'.//{{*}}{tag}')
                    if el is not None and el.text is not None and el.text.strip():
                        return el.text.strip()
                except Exception:
                    pass
                return default

            def find_all(parent, tag):
                """Поиск всех элементов с указанным тегом"""
                if parent is None: return []
                try:
                    return parent.findall(f'.//{{*}}{tag}')
                except Exception:
                    return []

            # === БАЗОВАЯ ИНФОРМАЦИЯ (ТОЛЬКО КОРНЕВЫЕ ТЕГИ!) ===
            profile_data["name"] = find_direct_text(root, "Name", "Unknown")
            profile_data["id"] = find_direct_text(root, "Id", "")
            profile_data["description"] = find_direct_text(root, "Description", "")
            profile_data["last_used"] = find_direct_text(root, "LastUsed", "")

            # === ОБСЕРВАТОРИЯ ===
            astro = find_section(root, "AstrometrySettings")
            if astro is not None:
                profile_data["observatory"] = {
                    "name": find_text(astro, "Observatory", ""),
                    "site": find_text(astro, "Site", ""),
                    "observer": find_text(astro, "Observer", ""),
                    "latitude": find_text(astro, "Latitude", ""),
                    "longitude": find_text(astro, "Longitude", ""),
                    "elevation": find_text(astro, "Elevation", ""),
                }

            # === КАМЕРА ===
            cam = find_section(root, "CameraSettings")
            if cam is not None:
                profile_data["camera"] = {
                    "device_name": find_text(cam, "LastDeviceName", ""),
                    "device_id": find_text(cam, "Id", ""),
                    "pixel_size": find_text(cam, "PixelSize", ""),
                    "gain": find_text(cam, "Gain", ""),
                    "offset": find_text(cam, "Offset", ""),
                    "temperature_target": find_text(cam, "Temperature", ""),
                    "bit_depth": find_text(cam, "BitDepth", ""),
                    "binning_x": find_text(cam, "BinningX", "1"),
                    "binning_y": find_text(cam, "BinningY", "1"),
                    "bulb_mode": find_text(cam, "BulbMode", ""),
                    "cooling_duration": find_text(cam, "CoolingDuration", ""),
                    "warming_duration": find_text(cam, "WarmingDuration", ""),
                    "timeout": find_text(cam, "Timeout", ""),
                    "raw_converter": find_text(cam, "RawConverter", ""),
                    "bayer_pattern": find_text(cam, "BayerPattern", ""),
                    "dew_heater_on": find_text(cam, "DewHeaterOn", ""),
                    "serial_port": find_text(cam, "SerialPort", ""),
                    "save_native_raw": find_text(cam, "SaveNativeCameraRaw", ""),
                }

            # === ТЕЛЕСКОП ===
            tel = find_section(root, "TelescopeSettings")
            if tel is not None:
                profile_data["telescope"] = {
                    "name": find_text(tel, "Name", ""),
                    "mount_name": find_text(tel, "MountName", ""),
                    "device_name": find_text(tel, "LastDeviceName", ""),
                    "device_id": find_text(tel, "Id", ""),
                    "focal_length": find_text(tel, "FocalLength", ""),
                    "focal_ratio": find_text(tel, "FocalRatio", ""),
                    "settle_time": find_text(tel, "SettleTime", ""),
                    "no_sync": find_text(tel, "NoSync", ""),
                    "primary_reversed": find_text(tel, "PrimaryReversed", ""),
                    "secondary_reversed": find_text(tel, "SecondaryReversed", ""),
                    "time_sync": find_text(tel, "TimeSync", ""),
                    "snap_port_start": find_text(tel, "SnapPortStart", ""),
                    "snap_port_stop": find_text(tel, "SnapPortStop", ""),
                }

            # === ФОКУСЁР ===
            foc = find_section(root, "FocuserSettings")
            if foc is not None:
                profile_data["focuser"] = {
                    "device_name": find_text(foc, "LastDeviceName", ""),
                    "device_id": find_text(foc, "Id", ""),
                    "af_step_size": find_text(foc, "AutoFocusStepSize", ""),
                    "af_method": find_text(foc, "AutoFocusMethod", ""),
                    "af_curve_fitting": find_text(foc, "AutoFocusCurveFitting", ""),
                    "af_exposure_time": find_text(foc, "AutoFocusExposureTime", ""),
                    "af_timeout": find_text(foc, "AutoFocusTimeoutSeconds", ""),
                    "af_attempts": find_text(foc, "AutoFocusTotalNumberOfAttempts", ""),
                    "af_frames_per_point": find_text(foc, "AutoFocusNumberOfFramesPerPoint", ""),
                    "af_inner_crop": find_text(foc, "AutoFocusInnerCropRatio", ""),
                    "af_outer_crop": find_text(foc, "AutoFocusOuterCropRatio", ""),
                    "af_binning": find_text(foc, "AutoFocusBinning", ""),
                    "af_initial_offset": find_text(foc, "AutoFocusInitialOffsetSteps", ""),
                    "af_disable_guiding": find_text(foc, "AutoFocusDisableGuiding", ""),
                    "backlash_out": find_text(foc, "BacklashOut", ""),
                    "backlash_in": find_text(foc, "BacklashIn", ""),
                    "backlash_model": find_text(foc, "BacklashCompensationModel", ""),
                    "settle_time": find_text(foc, "FocuserSettleTime", ""),
                    "use_filter_offsets": find_text(foc, "UseFilterWheelOffsets", ""),
                }

            # === КОЛЕСО ФИЛЬТРОВ ===
            fw = find_section(root, "FilterWheelSettings")
            if fw is not None:
                profile_data["filter_wheel"] = {
                    "device_name": find_text(fw, "LastDeviceName", ""),
                    "device_id": find_text(fw, "Id", ""),
                    "unidirectional": find_text(fw, "Unidirectional", ""),
                    "disable_guiding_on_change": find_text(fw, "DisableGuidingOnFilterChange", ""),
                }
                filters_list = []
                for f_info in find_all(fw, "FilterInfo"):
                    f_name = find_text(f_info, "_name", "")
                    f_pos = find_text(f_info, "_position", "")
                    f_offset = find_text(f_info, "_focusOffset", "0")
                    f_af_filter = find_text(f_info, "_autoFocusFilter", "")
                    f_af_offset = find_text(f_info, "_autoFocusOffset", "")
                    if f_name:
                        filters_list.append({
                            "name": f_name, "position": f_pos,
                            "focus_offset": f_offset,
                            "auto_focus_filter": f_af_filter,
                            "auto_focus_offset": f_af_offset,
                        })
                profile_data["filter_wheel"]["filters"] = filters_list

            # === ГИД ===
            guider = find_section(root, "GuiderSettings")
            if guider is not None:
                profile_data["guider"] = {
                    "name": find_text(guider, "GuiderName", ""),
                    "device_name": find_text(guider, "LastDeviceName", ""),
                    "dither_pixels": find_text(guider, "DitherPixels", ""),
                    "dither_ra_only": find_text(guider, "DitherRAOnly", ""),
                    "settle_time": find_text(guider, "SettleTime", ""),
                    "settle_pixels": find_text(guider, "SettlePixels", ""),
                    "settle_timeout": find_text(guider, "SettleTimeout", ""),
                    "auto_retry_start": find_text(guider, "AutoRetryStartGuiding", ""),
                    "auto_retry_timeout": find_text(guider, "AutoRetryStartGuidingTimeoutSeconds", ""),
                    "phd2_scale": find_text(guider, "PHD2GuiderScale", "PIXELS"),
                    "phd2_path": find_text(guider, "PHD2Path", ""),
                    "phd2_port": find_text(guider, "PHD2ServerPort", ""),
                    "phd2_url": find_text(guider, "PHD2ServerUrl", ""),
                    "phd2_instance": find_text(guider, "PHD2InstanceNumber", ""),
                }

            # === РОТАТОР ===
            rot = find_section(root, "RotatorSettings")
            if rot is not None:
                profile_data["rotator"] = {
                    "device_name": find_text(rot, "LastDeviceName", ""),
                    "device_id": find_text(rot, "Id", ""),
                    "range_type": find_text(rot, "RangeType", ""),
                    "reverse_2": find_text(rot, "Reverse2", ""),
                }

            # === ФАЙЛЫ ИЗОБРАЖЕНИЙ ===
            img = find_section(root, "ImageFileSettings")
            if img is not None:
                profile_data["image_settings"] = {
                    "file_path": find_text(img, "FilePath", ""),
                    "file_type": find_text(img, "FileType", ""),
                    "file_pattern": find_text(img, "FilePattern", ""),
                    "fits_compression": find_text(img, "FITSCompressionType", ""),
                    "tiff_compression": find_text(img, "TIFFCompressionType", ""),
                }

            # === ПОСЛЕДОВАТЕЛЬНОСТЬ ===
            seq = find_section(root, "SequenceSettings")
            if seq is not None:
                profile_data["sequence"] = {
                    "templates_folder": find_text(seq, "SequencerTemplatesFolder", ""),
                    "targets_folder": find_text(seq, "SequencerTargetsFolder", ""),
                    "default_folder": find_text(seq, "DefaultSequenceFolder", ""),
                    "startup_template": find_text(seq, "StartupSequenceTemplate", ""),
                    "do_meridian_flip": find_text(seq, "DoMeridianFlip", ""),
                    "park_mount_at_end": find_text(seq, "ParkMountAtSequenceEnd", ""),
                }

            # === PLATESOLVE ===
            ps = find_section(root, "PlateSolveSettings")
            if ps is not None:
                profile_data["platesolve"] = {
                    "solver_type": find_text(ps, "PlateSolverType", ""),
                    "blind_solver": find_text(ps, "BlindSolverType", ""),
                    "search_radius": find_text(ps, "SearchRadius", ""),
                    "exposure_time": find_text(ps, "ExposureTime", ""),
                    "binning": find_text(ps, "Binning", ""),
                    "gain": find_text(ps, "Gain", ""),
                    "attempts": find_text(ps, "NumberOfAttempts", ""),
                    "astap_location": find_text(ps, "ASTAPLocation", ""),
                    "astrometry_url": find_text(ps, "AstrometryURL", ""),
                }

            # === MERIDIAN FLIP ===
            mf = find_section(root, "MeridianFlipSettings")
            if mf is not None:
                profile_data["meridian_flip"] = {
                    "minutes_after_meridian": find_text(mf, "MinutesAfterMeridian", ""),
                    "max_minutes_after": find_text(mf, "MaxMinutesAfterMeridian", ""),
                    "pause_before": find_text(mf, "PauseTimeBeforeMeridian", ""),
                    "settle_time": find_text(mf, "SettleTime", ""),
                    "recenter": find_text(mf, "Recenter", ""),
                    "autofocus_after": find_text(mf, "AutoFocusAfterFlip", ""),
                    "rotate_image": find_text(mf, "RotateImageAfterFlip", ""),
                    "use_side_of_pier": find_text(mf, "UseSideOfPier", ""),
                }

            # === FLAT WIZARD ===
            flat_wiz = find_section(root, "FlatWizardSettings")
            if flat_wiz is not None:
                profile_data["flat_wizard"] = {
                    "mode": find_text(flat_wiz, "FlatWizardMode", ""),
                    "flat_count": find_text(flat_wiz, "FlatCount", ""),
                    "dark_flat_count": find_text(flat_wiz, "DarkFlatCount", ""),
                    "histogram_target": find_text(flat_wiz, "HistogramMeanTarget", ""),
                    "histogram_tolerance": find_text(flat_wiz, "HistogramTolerance", ""),
                    "open_when_done": find_text(flat_wiz, "OpenWhenDone", ""),
                }

            # === IMAGE SETTINGS ===
            img_set = find_section(root, "ImageSettings")
            if img_set is not None:
                profile_data["image_processing"] = {
                    "annotate_image": find_text(img_set, "AnnotateImage", ""),
                    "annotate_stars": find_text(img_set, "AnnotateUnlimitedStars", ""),
                    "detect_stars": find_text(img_set, "DetectStars", ""),
                    "auto_stretch": find_text(img_set, "AutoStretch", ""),
                    "debayer": find_text(img_set, "DebayerImage", ""),
                    "noise_reduction": find_text(img_set, "NoiseReduction", ""),
                }

            # === APPLICATION ===
            app_set = find_section(root, "ApplicationSettings")
            if app_set is not None:
                profile_data["application"] = {
                    "culture": find_text(app_set, "Culture", ""),
                    "log_level": find_text(app_set, "LogLevel", ""),
                    "polling_interval": find_text(app_set, "DevicePollingInterval", ""),
                    "page_size": find_text(app_set, "PageSize", ""),
                }

            self.nina_profile = profile_data
            # Защита от двойного лога
            profile_log_key = f"{profile_data.get('name', '?')}|{profile_data.get('id', '')[:8]}"
            if self._last_profile_log != profile_log_key:
                self._last_profile_log = profile_log_key
                self.log(f"Профиль: {profile_data.get('name', '?')} (ID: {profile_data.get('id', '')[:8]})", "INFO")
            self._broadcast({"type": "profile", "data": self.nina_profile})
        except Exception as e:
            self.log(f"Ошибка парсинга профиля: {e}", "ERROR")
            import traceback
            traceback.print_exc()

    def _broadcast(self, message: dict):
        """Отправка сообщения через callback"""
        if self.broadcast_callback:
            self.broadcast_callback(message)

    # ===================================================================
    # ФОНОВЫЕ ЗАДАЧИ (все 7 потоков)
    # ===================================================================
    def _check_connections_thread(self):
        """Поток проверки подключения к NINA и Ollama"""
        while self.is_running:
            try:
                status_data = self._nina_request("equipment/info", silent_errors=True)
                if status_data:
                    self.nina_error_count = 0
                    if not self.nina_connected:
                        self.nina_connected = True
                        self.log("NINA подключена", "INFO")
                    self._update_equipment_registry(status_data)
                else:
                    self.nina_error_count += 1
                    if self.nina_connected and self.nina_error_count >= self.NINA_ERROR_THRESHOLD:
                        self.nina_connected = False
                        self.log("NINA отключена", "WARNING")
                        self._update_equipment_registry(None)
                try:
                    response = requests.get(f"{self.ollama_url}/api/tags", timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        new_models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                        if new_models != self.available_models:
                            self.available_models = new_models
                        self.ollama_error_count = 0
                        if not self.ollama_connected:
                            self.ollama_connected = True
                            self.log(f"Ollama подключен. Моделей: {len(self.available_models)}", "INFO")
                except Exception:
                    self.ollama_error_count += 1
                    if self.ollama_connected and self.ollama_error_count >= self.OLLAMA_ERROR_THRESHOLD:
                        self.ollama_connected = False
                        self.log("Ollama отключен", "WARNING")
                self.broadcast_equipment_update()
            except Exception as e:
                logger.error(f"Check connections error: {e}")
            time.sleep(10)

    def _monitor_equipment_thread(self):
        """Поток мониторинга детальной телеметрии оборудования"""
        while self.is_running:
            try:
                if self.nina_connected:
                    self._update_detailed_telemetry()
                else:
                    if self.detailed_telemetry.get("_connected", True):
                        self.detailed_telemetry = {"_connected": False}
                        self._broadcast({"type": "detailed_telemetry", "data": self.detailed_telemetry})
            except Exception as e:
                logger.error(f"Monitor equipment error: {e}")
            time.sleep(5)

    def _monitor_session_thread(self):
        """Поток мониторинга сессии (кадры, гид, среда)"""
        while self.is_running:
            try:
                if self.nina_connected:
                    self._fetch_image_stats()
                    self._fetch_guider_details()
                    self._fetch_environment()
            except Exception as e:
                logger.error(f"Monitor session error: {e}")
            time.sleep(5)

    def _monitor_profile_thread(self):
        """Поток мониторинга изменений файла профиля"""
        last_mtime = 0
        while self.is_running:
            try:
                if self.profile_path and os.path.exists(self.profile_path):
                    mtime = os.path.getmtime(self.profile_path)
                    if mtime > last_mtime:
                        last_mtime = mtime
                        self.load_nina_profile()
            except Exception as e:
                logger.error(f"Monitor profile error: {e}")
            time.sleep(10)

    def _monitor_sequence_thread(self):
        """Поток мониторинга последовательности"""
        while self.is_running:
            try:
                if self.nina_connected or self.nina_profile.get("sequence", {}).get("startup_template"):
                    tree = self.build_sequence_tree()
                    if tree:
                        self._broadcast({"type": "sequence_tree", "data": tree})
                    dash = self.get_sequence_dashboard()
                    if dash:
                        self._broadcast({"type": "sequence_state", "data": dash})
            except Exception as e:
                logger.error(f"Monitor sequence error: {e}")
            time.sleep(5)

    def _monitor_metrics_thread(self):
        """Поток сбора Prometheus-метрик"""
        prom_cfg = self.settings.get("prometheus", {})
        if not prom_cfg.get("enabled", True):
            return
        interval = prom_cfg.get("scrape_interval_seconds", 5)
        while self.is_running:
            try:
                self.prometheus.collect_from_backend()
                self.prometheus.record_history()
            except Exception as e:
                logger.error(f"Metrics collect error: {e}")
            time.sleep(interval)

    def _monitor_session_metadata_thread(self):
        """Поток парсинга Session Metadata"""
        sm_cfg = self.settings.get("session_metadata", {})
        if not sm_cfg.get("enabled", True):
            return
        interval = sm_cfg.get("scan_interval_seconds", 10)
        last_broadcast_count = -1
        while self.is_running:
            try:
                self.session_metadata.parse_all()
                current_count = len(self.session_metadata.image_metadata)
                if current_count != last_broadcast_count:
                    last_broadcast_count = current_count
                    summary = self.session_metadata.get_session_summary()
                    self._broadcast({"type": "session_metadata", "data": summary})
            except Exception as e:
                logger.error(f"Session metadata error: {e}")
            time.sleep(interval)

    def _update_equipment_registry(self, status_data: Optional[Dict] = None):
        """Обновление реестра оборудования"""
        registry = {}
        if status_data and isinstance(status_data, dict):
            if "Response" in status_data and isinstance(status_data["Response"], dict):
                status_data = status_data["Response"]
            categories = ["Camera", "Mount", "Focuser", "FilterWheel", "Guider", "Rotator", "Weather"]
            for cat in categories:
                if cat in status_data and isinstance(status_data[cat], dict):
                    dev = status_data[cat]
                    registry[cat] = {"Name": dev.get("Name", "Unknown"), "Connected": dev.get("Connected", False), "Data": dev}
            fw_data = self._nina_request("equipment/filterwheel/info", silent_errors=True)
            if fw_data:
                info = fw_data.get("Response", fw_data)
                if isinstance(info, dict):
                    registry["FilterWheel"] = {"Name": info.get("Name", "Unknown"), "Connected": info.get("Connected", False), "Data": info}
                    available = info.get("AvailableFilters", [])
                    filter_map, filter_names = {}, []
                    if isinstance(available, list):
                        for f in available:
                            if isinstance(f, dict):
                                name, f_id = f.get("Name"), f.get("Id")
                                if name is not None and f_id is not None:
                                    filter_names.append(str(name))
                                    filter_map[str(name)] = int(f_id)
                    if filter_names:
                        registry["Filters"] = filter_names
                        registry["FilterMap"] = filter_map
            registry.setdefault("Filters", [])
        self.equipment_registry = registry
        self.broadcast_equipment_update()

    def _fetch_image_stats(self):
        """Получение статистики последнего кадра"""
        try:
            data = self._nina_request("prepared-image/info", "GET", silent_errors=True)
            if data:
                resp = data.get("Response", data)
                if resp and isinstance(resp, dict):
                    stats = self._extract_image_stats(resp)
                    if stats:
                        self.image_stats = stats
                        self._update_session_stats(stats)
                        self.image_history.append(stats)
                        if len(self.image_history) > 200:
                            self.image_history = self.image_history[-200:]
                        self._log_stats_to_csv(stats)
                        self._broadcast({
                            "type": "image_stats",
                            "data": {
                                "current": self.image_stats,
                                "session": self.session_stats,
                                "history": self.image_history[-50:]
                            }
                        })
        except Exception:
            pass

    def _extract_image_stats(self, data: Dict) -> Optional[Dict]:
        """Извлечение статистики из данных кадра"""
        if not data or not isinstance(data, dict):
            return None
        stats = {"timestamp": datetime.now().isoformat()}
        stat_keys = {
            "hfr": ["HFR", "Hfr"], "fwhm": ["FWHM", "Fwhm"],
            "stars": ["StarCount", "Stars"], "mean": ["Mean", "MeanBrightness"],
            "exposure": ["ExposureTime", "Exposure"], "filter": ["Filter", "FilterName"],
            "temperature": ["Temperature", "SensorTemperature"],
            "gain": ["Gain"], "offset": ["Offset"],
        }
        for key, candidates in stat_keys.items():
            for cand in candidates:
                val = self._deep_get(data, cand)
                if val is not None:
                    stats[key] = val
                    break
        return stats if len(stats) > 2 else None

    def _deep_get(self, d: Any, key: str) -> Any:
        """Рекурсивный поиск ключа в словаре"""
        if isinstance(d, dict):
            if key in d:
                return d[key]
            for v in d.values():
                r = self._deep_get(v, key)
                if r is not None:
                    return r
        elif isinstance(d, list):
            for item in d:
                r = self._deep_get(item, key)
                if r is not None:
                    return r
        return None

    def _update_session_stats(self, stats: Dict):
        """Обновление статистики сессии"""
        try:
            hfr = stats.get("hfr")
            if hfr is not None:
                hfr_val = float(hfr)
                self.session_stats["current_hfr"] = hfr_val
                prev = self.session_stats["avg_hfr"] or hfr_val
                self.session_stats["avg_hfr"] = round((prev * 0.9 + hfr_val * 0.1), 2)
                if self.session_stats["best_hfr"] is None or hfr_val < self.session_stats["best_hfr"]:
                    self.session_stats["best_hfr"] = round(hfr_val, 2)
                if self.session_stats["worst_hfr"] is None or hfr_val > self.session_stats["worst_hfr"]:
                    self.session_stats["worst_hfr"] = round(hfr_val, 2)
            if stats.get("exposure") is not None:
                self.session_stats["total_exposure_time"] += float(stats["exposure"])
                self.session_stats["total_frames"] += 1
        except Exception:
            pass

    def _log_stats_to_csv(self, stats: Dict):
        """Логирование статистики в CSV файл"""
        try:
            csv_dir = Path("logs/stats")
            csv_dir.mkdir(parents=True, exist_ok=True)
            csv_file = csv_dir / f"stats_{datetime.now().strftime('%Y%m%d')}.csv"
            file_exists = csv_file.exists()
            with open(csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['timestamp', 'exposure', 'gain', 'offset', 'filter',
                                     'hfr', 'fwhm', 'stars', 'mean', 'temperature'])
                writer.writerow([
                    stats.get('timestamp', ''), stats.get('exposure', ''),
                    stats.get('gain', ''), stats.get('offset', ''),
                    stats.get('filter', ''), stats.get('hfr', ''),
                    stats.get('fwhm', ''), stats.get('stars', ''),
                    stats.get('mean', ''), stats.get('temperature', ''),
                ])
        except Exception as e:
            logger.error(f"CSV log error: {e}")

    def _calculate_pixel_scale(self) -> Optional[float]:
        """Расчёт pixel scale в arcsec/pixel"""
        try:
            pixel_size = float(self.nina_profile.get("camera", {}).get("pixel_size", 0))
            focal_length = float(self.nina_profile.get("telescope", {}).get("focal_length", 0))
            if pixel_size > 0 and focal_length > 0:
                return (pixel_size * 206.265) / focal_length
        except Exception:
            pass
        try:
            return float(self.settings.get("guider_pixel_scale", 1.0))
        except Exception:
            return 1.0

    def _fetch_guider_details(self):
        """Получение детальной информации о гиде"""
        try:
            data = self._nina_request("equipment/guider/info", "GET", silent_errors=True)
            if data:
                resp = data.get("Response", data)
                if resp and isinstance(resp, dict):
                    pixel_scale = self._calculate_pixel_scale()
                    rms_total_px = resp.get("RMSTotal", resp.get("RmsTotal"))
                    rms_ra_px = resp.get("RMSRA", resp.get("RmsRa"))
                    rms_dec_px = resp.get("RMSDec", resp.get("RmsDec"))
                    if pixel_scale and self.guider_unit == "arcsec":
                        rms_total = round(float(rms_total_px) * pixel_scale, 2) if rms_total_px else None
                        rms_ra = round(float(rms_ra_px) * pixel_scale, 2) if rms_ra_px else None
                        rms_dec = round(float(rms_dec_px) * pixel_scale, 2) if rms_dec_px else None
                    else:
                        rms_total = rms_total_px
                        rms_ra = rms_ra_px
                        rms_dec = rms_dec_px
                    self.guider_details = {
                        "is_guiding": resp.get("IsGuiding", False) or resp.get("Guiding", False),
                        "rms_total": rms_total, "rms_ra": rms_ra, "rms_dec": rms_dec,
                        "pixel_scale": pixel_scale, "unit": self.guider_unit,
                        "timestamp": datetime.now().isoformat(),
                    }
                    self._broadcast({"type": "guider_details", "data": self.guider_details})
                    self.detailed_telemetry["guider"] = self.guider_details
                    self._broadcast({"type": "detailed_telemetry", "data": self.detailed_telemetry})
        except Exception:
            pass

    def _fetch_environment(self):
        """Получение данных об окружающей среде"""
        env = {"source": "unknown", "timestamp": datetime.now().isoformat()}
        try:
            data = self._nina_request("equipment/weather/info", "GET", silent_errors=True)
            if data:
                resp = data.get("Response", data)
                if resp and isinstance(resp, dict) and resp.get("Connected", False):
                    env.update({
                        "source": "weather_station", "connected": True,
                        "name": resp.get("Name", ""),
                        "temperature": resp.get("Temperature"),
                        "humidity": resp.get("Humidity"),
                        "pressure": resp.get("Pressure"),
                        "cloud_cover": resp.get("CloudCover"),
                        "wind_speed": resp.get("WindSpeed"),
                        "dew_point": resp.get("DewPoint"),
                        "safe": resp.get("IsSafe", resp.get("Safe")),
                    })
                    self.environment_data = env
                    self._broadcast({"type": "environment", "data": env})
                    return
        except Exception:
            pass
        try:
            data = self._nina_request("equipment/focuser/info", "GET", silent_errors=True)
            if data:
                resp = data.get("Response", data)
                if resp and isinstance(resp, dict):
                    temp = resp.get("Temperature")
                    if temp is not None:
                        self.focuser_ambient_temp = float(temp)
                        env.update({
                            "source": "focuser_sensor",
                            "connected": False,
                            "temperature": self.focuser_ambient_temp,
                        })
                        self.environment_data = env
                        self._broadcast({"type": "environment", "data": env})
        except Exception:
            pass

    def _update_detailed_telemetry(self):
        """Обновление детальной телеметрии всех устройств"""
        modules = self.settings.get("modules", {})
        self.detailed_telemetry["_connected"] = True
        
        if modules.get("camera", True):
            try:
                data = self._nina_request("equipment/camera/info", "GET", silent_errors=True)
                if data:
                    cam = data.get("Response", data)
                    if cam and isinstance(cam, dict):
                        self.detailed_telemetry["camera"] = {
                            "name": cam.get("Name", ""),
                            "connected": cam.get("Connected", False),
                            "temperature": cam.get("Temperature"),
                            "target_temp": cam.get("TargetTemperature", cam.get("TemperatureSetPoint")),
                            "cooler_on": cam.get("CoolerOn", cam.get("Cooling", False)),
                            "cooler_power": cam.get("CoolerPower"),
                            "is_exposing": cam.get("IsExposing", False),
                            "gain": cam.get("Gain"),
                            "offset": cam.get("Offset"),
                            "binning_x": cam.get("BinX", 1),
                            "binning_y": cam.get("BinY", 1),
                            "pixel_size": cam.get("PixelSize"),
                        }
            except Exception:
                pass
                
        if modules.get("mount", True):
            try:
                data = self._nina_request("equipment/mount/info", "GET", silent_errors=True)
                if data:
                    mnt = data.get("Response", data)
                    if mnt and isinstance(mnt, dict):
                        tracking_mode = mnt.get("TrackingMode", mnt.get("TrackingRate"))
                        tracking_names = {0: "Sidereal", 1: "Lunar", 2: "Solar", 3: "King", 5: "Stop"}
                        tracking_display = tracking_names.get(tracking_mode, str(tracking_mode)) if tracking_mode is not None else "—"
                        self.detailed_telemetry["mount"] = {
                            "name": mnt.get("Name", ""),
                            "connected": mnt.get("Connected", False),
                            "right_ascension": mnt.get("RightAscension", mnt.get("RA")),
                            "declination": mnt.get("Declination", mnt.get("Dec")),
                            "slewing": mnt.get("Slewing", False),
                            "tracking": mnt.get("Tracking", False),
                            "tracking_mode": tracking_display,
                            "parked": mnt.get("Parked", False),
                            "pier_side": mnt.get("SideOfPier", mnt.get("PierSide")),
                        }
            except Exception:
                pass
                
        if modules.get("focuser", True):
            try:
                data = self._nina_request("equipment/focuser/info", "GET", silent_errors=True)
                if data:
                    foc = data.get("Response", data)
                    if foc and isinstance(foc, dict):
                        self.detailed_telemetry["focuser"] = {
                            "name": foc.get("Name", ""),
                            "connected": foc.get("Connected", False),
                            "position": foc.get("Position"),
                            "moving": foc.get("Moving", False),
                            "temperature": foc.get("Temperature"),
                        }
            except Exception:
                pass
                
        if modules.get("filters", True):
            try:
                data = self._nina_request("equipment/filterwheel/info", "GET", silent_errors=True)
                if data:
                    fw = data.get("Response", data)
                    if fw and isinstance(fw, dict):
                        self.detailed_telemetry["filters"] = {
                            "name": fw.get("Name", ""),
                            "connected": fw.get("Connected", False),
                            "selected_filter": fw.get("SelectedFilter"),
                            "available_filters": fw.get("AvailableFilters", []),
                            "filter_count": len(fw.get("AvailableFilters", [])),
                        }
            except Exception:
                pass
                
        if modules.get("rotator", False):
            try:
                data = self._nina_request("equipment/rotator/info", "GET", silent_errors=True)
                if data:
                    rot = data.get("Response", data)
                    if rot and isinstance(rot, dict) and rot.get("Connected"):
                        self.detailed_telemetry["rotator"] = {
                            "name": rot.get("Name", ""),
                            "connected": True,
                            "position": rot.get("Position"),
                            "moving": rot.get("Moving", False),
                        }
            except Exception:
                pass
                
        self._broadcast({"type": "detailed_telemetry", "data": self.detailed_telemetry})

    # ===================================================================
    # ЛОГИ И ЧАТ
    # ===================================================================
    def log(self, message: str, level: str = "INFO"):
        """Логирование сообщения с учётом уровня"""
        levels = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}
        current_lvl = levels.get(self.settings.get("log_level", "INFO"), 20)
        msg_lvl = levels.get(level, 20)
        if msg_lvl < current_lvl:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {"time": timestamp, "level": level, "message": message}
        self.log_history.append(log_entry)
        if len(self.log_history) > 500:
            self.log_history = self.log_history[-500:]
        logger.log(msg_lvl, message)
        self._broadcast({"type": "log", "data": log_entry})

    def add_to_chat(self, sender: str, message: str, msg_id: Optional[str] = None):
        """Добавление сообщения в чат"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        msg_id_final = msg_id or f"{timestamp}-{sender}-{hash(message) % 10000}"
        chat_entry = {"time": timestamp, "sender": sender, "message": message, "id": msg_id_final}
        self.chat_history.append(chat_entry)
        max_len = self.max_chat_history * 2
        if len(self.chat_history) > max_len:
            self.chat_history = self.chat_history[-max_len:]
        self._broadcast({"type": "chat", "data": chat_entry})

    def update_ai_status(self, thinking: bool = False):
        """Обновление статуса AI"""
        self.is_ai_thinking = thinking
        if thinking:
            self.current_ai_start_time = time.time()
            self.ai_requests_count += 1
        else:
            if self.current_ai_start_time:
                self.last_ai_response_time = datetime.now()
                self.ai_success_count += 1
                self.current_ai_start_time = None
        self._broadcast({
            "type": "ai_status",
            "data": {
                "thinking": self.is_ai_thinking,
                "last_response": self.last_ai_response_time.isoformat() if self.last_ai_response_time else None,
                "requests_count": self.ai_requests_count,
                "errors_count": self.ai_errors_count,
                "success_count": self.ai_success_count,
                "mode": self.ai_mode
            }
        })

    def broadcast_equipment_update(self):
        """Broadcast обновления оборудования"""
        self._broadcast({
            "type": "equipment",
            "data": {
                "registry": self.equipment_registry,
                "nina_connected": self.nina_connected,
                "ollama_connected": self.ollama_connected,
                "model": self.model,
                "host": self.nina_host,
                "port": self.nina_port,
                "ollama_url": self.ollama_url
            }
        })

    def _nina_request(self, endpoint: str, method: str = "GET", data: Any = None,
                      silent_errors: bool = False, custom_timeout: Optional[int] = None) -> Optional[Dict]:
        """HTTP запрос к NINA API"""
        url = f"http://{self.nina_host}:{self.nina_port}/v2/api/{endpoint}"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        timeout = custom_timeout if custom_timeout else 30
        if "capture" in endpoint and isinstance(data, dict):
            try:
                dur = float(data.get("duration", 10))
                if str(data.get("waitForResult", "false")).lower() == "true":
                    timeout = max(dur + 240, 60)
            except ValueError:
                pass
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=timeout, params=data if isinstance(data, dict) else None)
            elif method.upper() == "POST":
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method.upper() == "PUT":
                response = requests.put(url, json=data, headers=headers, timeout=timeout)
            else:
                response = requests.request(method, url, json=data, headers=headers, timeout=timeout)
            response.raise_for_status()
            try:
                result = response.json()
            except Exception:
                return {"Success": True, "Response": response.text}
            if isinstance(result, dict):
                is_error = False
                error_msg = ""
                if result.get("Success") is False:
                    is_error = True
                    error_msg = result.get("Error") or result.get("Message") or "Неизвестная ошибка"
                elif result.get("Error"):
                    is_error = True
                    error_msg = result.get("Error")
                if is_error:
                    if silent_errors and "not connected" in str(error_msg).lower():
                        return result
                    self.prometheus.inc("nina_api_errors_total", labels={"endpoint": endpoint})
                    self.log(f"NINA ({endpoint}): {error_msg}", "WARNING")
                else:
                    self.prometheus.inc("nina_api_requests_total", labels={"endpoint": endpoint})
                if "Response" not in result and not is_error:
                    return result
                if is_error:
                    return None
                return result
        except Exception as e:
            if not silent_errors:
                self.log(f"API ({endpoint}): {str(e)}", "ERROR")
            return None

    def _wait_for_mount_idle(self, timeout: int = 240) -> bool:
        """Ожидание завершения движения монтировки"""
        start = time.time()
        while self.is_running and (time.time() - start) < timeout:
            info = self._nina_request("equipment/mount/info", "GET", silent_errors=True)
            if info:
                resp = info.get("Response", info)
                if not resp.get("Slewing", False):
                    return True
            time.sleep(1.0)
        return False

    def _wait_for_camera_idle(self, timeout: int = 1200) -> bool:
        """Ожидание завершения экспозиции"""
        start = time.time()
        while self.is_running and (time.time() - start) < timeout:
            info = self._nina_request("equipment/camera/info", "GET", silent_errors=True)
            if info:
                resp = info.get("Response", info)
                if not resp.get("IsExposing", False) and resp.get("CameraState", 0) == 0:
                    return True
            time.sleep(0.5)
        return False

    # ===================================================================
    # ПОСЛЕДОВАТЕЛЬНОСТЬ (Advanced Sequence Parser из v9)
    # ===================================================================
    def build_sequence_tree(self) -> List[Dict]:
        """Построение дерева последовательности с полным парсингом"""
        data = self._nina_request("sequence/json", "GET", silent_errors=True)
        root = None
        if data:
            root = data.get("Response", data)
        # Fallback: чтение из файла
        if not root or not isinstance(root, dict):
            file_path = self.nina_profile.get("sequence", {}).get("startup_template", "")
            if file_path and os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        root = json.load(f)
                    source_key = f"file:{file_path}"
                    if self._last_sequence_source != source_key:
                        self._last_sequence_source = source_key
                        self.log(f"Последовательность прочитана: {os.path.basename(file_path)}", "INFO")
                except Exception as e:
                    self.log(f"Ошибка чтения файла последовательности: {e}", "WARNING")
        if not root or not isinstance(root, dict):
            self.sequence_tree = []
            return []

        # Получение активного элемента из state API
        state_data = self._nina_request("sequence/state", "GET", silent_errors=True)
        active_info = {}
        active_path = None
        if state_data:
            state_resp = state_data.get("Response", state_data)
            if isinstance(state_resp, dict):
                active_info = self._find_active_instruction(state_resp)
                active_path = active_info.get("path")

        tree = []

        def get_readable_type(type_str: str) -> str:
            """Преобразование типа в читаемое имя"""
            if not type_str:
                return "Элемент"
            short = type_str.split('.')[-1] if '.' in type_str else type_str
            return TYPE_NAMES.get(short, short)

        def extract_expression(node: Dict, field: str) -> Optional[str]:
            """Извлечение значения из Expression-объекта"""
            expr = node.get(field)
            if expr is None:
                return None
            if isinstance(expr, dict):
                def_ = expr.get("Definition")
                if def_ is not None and str(def_).strip():
                    return str(def_).strip()
            if isinstance(expr, (str, int, float)):
                return str(expr)
            return None

        def extract_node_details(node: Dict) -> Dict[str, Any]:
            """Извлечение всех деталей узла"""
            details = {}
            type_str = node.get("$type", "")
            readable = get_readable_type(type_str)
            name = node.get("Name") or node.get("Text") or node.get("Identifier") or readable
            details["display_name"] = name
            details["readable_type"] = readable
            details["raw_type"] = type_str.split('.')[-1] if '.' in type_str else type_str

            params = []
            
            # ExposureTime
            exp_time = extract_expression(node, "ExposureTimeExpression") or node.get("ExposureTime")
            if exp_time is not None and str(exp_time).strip():
                try:
                    params.append(f"{float(exp_time):.1f}s")
                except (ValueError, TypeError):
                    params.append(f"{exp_time}s")

            # Iterations
            completed = node.get("CompletedIterations")
            iterations = extract_expression(node, "IterationsExpression") or node.get("Iterations")
            if completed is not None and iterations is not None:
                params.append(f"{completed}/{iterations}")
            elif iterations is not None:
                params.append(f"×{iterations}")

            # Temperature
            temp = extract_expression(node, "TemperatureExpression") or node.get("Temperature")
            if temp is not None and str(temp).strip() and "Temperature" in type_str:
                try:
                    params.append(f"{float(temp)}°C")
                except (ValueError, TypeError):
                    params.append(f"{temp}°C")

            # Duration (WaitForTimeSpan)
            dur = extract_expression(node, "TimeExpression")
            if dur is None:
                t_def = node.get("TimeDefinition")
                if t_def is not None:
                    dur = t_def
            if dur is not None and "WaitForTimeSpan" in type_str:
                try:
                    params.append(f"{float(dur)}с")
                except (ValueError, TypeError):
                    params.append(f"{dur}")

            # Position (MoveFocuserAbsolute)
            pos = extract_expression(node, "PositionExpression") or node.get("Position")
            if pos is not None and "Focuser" in type_str:
                params.append(f"Pos {pos}")

            # SelectedDevice
            dev = node.get("SelectedDevice")
            if dev:
                dev_ru = DEVICE_NAMES.get(dev, dev)
                params.append(dev_ru)

            # ComboBoxText (SwitchFilter)
            cb = node.get("ComboBoxText")
            if cb:
                params.append(f"Фильтр: {cb}")

            # TrackingMode
            tm = node.get("TrackingMode")
            if tm is not None and "Tracking" in type_str:
                params.append(f"Трекинг: {TRACKING_MODES.get(tm, str(tm))}")

            # Binning
            binning = node.get("Binning")
            if binning:
                if isinstance(binning, dict):
                    bx = binning.get("X", 1)
                    by = binning.get("Y", 1)
                    params.append(f"Bin {bx}x{by}")
                elif isinstance(binning, str):
                    params.append(f"Bin {binning}")

            # ImageType
            img_type = node.get("ImageType")
            if img_type:
                params.append(IMAGE_TYPES.get(img_type, img_type))

            # Target
            target = node.get("Target")
            if isinstance(target, dict):
                t_name = target.get("TargetName") or ""
                if not t_name:
                    ic = target.get("InputCoordinates", {})
                    if ic and (ic.get("RAHours") or ic.get("DecDegrees")):
                        t_name = f"RA{ic.get('RAHours', 0)}h Dec{ic.get('DecDegrees', 0)}°"
                if t_name:
                    params.append(f"Цель: {t_name}")

            # Coordinates (SlewScopeToAltAz)
            coords = node.get("Coordinates")
            if isinstance(coords, dict) and "SlewScopeToAltAz" in type_str:
                alt = extract_expression(node, "AltExpression") or coords.get("AltDegrees")
                az = extract_expression(node, "AzExpression") or coords.get("AzDegrees")
                if alt is not None and az is not None:
                    params.append(f"Alt {alt}° Az {az}°")

            # WaitForAltitude
            if "WaitForAltitude" in type_str:
                offset = extract_expression(node, "OffsetExpression") or node.get("Offset")
                cmp = node.get("AboveOrBelow", ">")
                if offset is not None:
                    params.append(f"Alt {cmp} {offset}°")

            # WaitForTime
            if "WaitForTime" in type_str and "WaitForTimeSpan" not in type_str:
                h = node.get("Hours")
                m = node.get("Minutes")
                s = node.get("Seconds")
                if h is not None:
                    params.append(f"{h:02d}:{m or 0:02d}:{s or 0:02d}")
                provider = node.get("SelectedProvider")
                if isinstance(provider, dict):
                    ptype = provider.get("$type", "").split('.')[-1]
                    params.append(ptype.replace("Provider", ""))

            # GlobalVariable
            if "GlobalVariable" in type_str:
                identifier = node.get("Identifier")
                orig_def = node.get("OriginalDefinition")
                if identifier:
                    params.append(f"{identifier} = {orig_def if orig_def else '?'}")

            # TwoPointPolarAlignment
            if "TwoPointPolarAlignment" in type_str:
                rotation = node.get("RotationAmount")
                exp_t = node.get("ExposureTime")
                gain = node.get("Gain")
                method = node.get("Method")
                if rotation is not None:
                    params.append(f"Rotate {rotation}°")
                if exp_t is not None:
                    params.append(f"Exp {exp_t}s")
                if gain is not None:
                    params.append(f"Gain {gain}")
                if method is not None:
                    params.append(POLAR_ALIGN_METHODS.get(method, f"Method {method}"))

            # Dither
            if type_str and "Dither" in type_str and "After" not in type_str:
                params.append("Dither")

            # DitherAfterExposures
            if "DitherAfterExposures" in type_str:
                after = extract_expression(node, "AfterExposuresExpression") or node.get("AfterExposures")
                if after is not None:
                    params.append(f"каждые {after} кадров")

            # Autofocus triggers
            if "AutofocusAfter" in type_str:
                amount = extract_expression(node, "AmountExpression") or node.get("Amount")
                if amount is not None:
                    if "Temperature" in type_str:
                        params.append(f"ΔT={amount}°C")
                    elif "HFR" in type_str:
                        params.append(f"ΔHFR={amount}%")
                    elif "Time" in type_str:
                        params.append(f"каждые {amount} мин")
                    elif "Filter" in type_str:
                        params.append("при смене фильтра")

            # MeridianFlip
            if "MeridianFlipTrigger" in type_str:
                params.append("Меридиан")

            # CenterAfterDriftTrigger
            if "CenterAfterDriftTrigger" in type_str:
                dist = extract_expression(node, "DistanceArcMinutesExpression") or node.get("DistanceArcMinutes")
                after = extract_expression(node, "AfterExposuresExpression") or node.get("AfterExposures")
                if dist is not None:
                    params.append(f"дрейф >{dist}'")
                if after is not None:
                    params.append(f"каждые {after} кадров")

            # InterruptWhenRMSAbove
            if "InterruptWhenRMSAbove" in type_str:
                thresh = node.get("RmsThreshold")
                minpts = node.get("MinimumPoints")
                if thresh is not None:
                    params.append(f"RMS > {thresh}\"")
                if minpts is not None:
                    params.append(f"мин {minpts} точек")

            # FlexureCompensator
            if "FlexureCompensator" in type_str:
                after = node.get("AfterExposures")
                if after is not None:
                    params.append(f"каждые {after} кадров")

            # Phd2Settle
            if "Phd2Settle" in type_str:
                params.append("Settle PHD2")

            # ErrorBehavior и Attempts
            eb = node.get("ErrorBehavior")
            attempts = node.get("Attempts")
            if eb is not None or attempts is not None:
                if eb is not None and eb != 0:
                    eb_ru = ERROR_BEHAVIORS_RU.get(eb, str(eb))
                    params.append(f"Ошибка: {eb_ru}")
                if attempts is not None and attempts > 1:
                    params.append(f"Попыток: {attempts}")

            details["params"] = params
            details["info_str"] = " | ".join(params) if params else ""
            return details

        def is_container_node(node: Dict) -> bool:
            """Проверка, является ли узел контейнером"""
            type_str = node.get("$type", "")
            short = type_str.split('.')[-1] if '.' in type_str else type_str
            return "Container" in short

        def get_status(node: Dict, path: str) -> str:
            """Определение статуса узла"""
            status = str(node.get("Status", "")).upper()
            if status == "RUNNING":
                return "running"
            if status in ["FINISHED", "COMPLETED", "SUCCESS", "SKIPPED"]:
                return "completed"
            if active_path and path == active_path:
                return "running"
            return "pending"

        def build_path(parent_path: str, name: str) -> str:
            """Построение пути к узлу"""
            return f"{parent_path}/{name}" if parent_path else name

        def traverse(node, depth, parent_path=""):
            """Рекурсивный обход дерева"""
            if not node or not isinstance(node, dict):
                return
            details = extract_node_details(node)
            path = build_path(parent_path, details["display_name"])
            status = get_status(node, path)
            is_cont = is_container_node(node)

            tree.append({
                "name": details["display_name"],
                "readable_type": details["readable_type"],
                "raw_type": details["raw_type"],
                "depth": depth,
                "status": status,
                "info": details["info_str"],
                "params": details["params"],
                "is_container": is_cont,
                "type": details["raw_type"],
                "path": path,
                "is_active": (active_path and path == active_path) or status == "running",
                "error_behavior": node.get("ErrorBehavior"),
                "attempts": node.get("Attempts"),
                "iterations": node.get("Iterations"),
                "completed_iterations": node.get("CompletedIterations"),
            })

            # Обход Items
            items = node.get("Items")
            if isinstance(items, dict):
                values = items.get("$values", [])
                if isinstance(values, list):
                    for child in values:
                        traverse(child, depth + 1, path)
            elif isinstance(items, list):
                for child in items:
                    traverse(child, depth + 1, path)

            # Обход Triggers
            triggers = node.get("Triggers")
            if isinstance(triggers, dict):
                values = triggers.get("$values", [])
                if isinstance(values, list) and values:
                    trig_path = build_path(path, "Triggers")
                    tree.append({
                        "name": f"Триггеры ({len(values)})",
                        "readable_type": "TriggersGroup",
                        "raw_type": "TriggersGroup",
                        "depth": depth + 1,
                        "status": "pending",
                        "info": f"{len(values)} шт.",
                        "params": [],
                        "is_container": True,
                        "type": "TriggersGroup",
                        "path": trig_path,
                        "is_active": False,
                    })
                    for trig in values:
                        traverse(trig, depth + 2, trig_path)

            # Обход Conditions
            conditions = node.get("Conditions")
            if isinstance(conditions, dict):
                values = conditions.get("$values", [])
                if isinstance(values, list) and values:
                    cond_path = build_path(path, "Conditions")
                    cond_infos = []
                    for cond in values:
                        if isinstance(cond, dict):
                            cond_infos.append(get_readable_type(cond.get("$type", "")))
                    tree.append({
                        "name": f"Условия ({len(values)})",
                        "readable_type": "ConditionsGroup",
                        "raw_type": "ConditionsGroup",
                        "depth": depth + 1,
                        "status": "pending",
                        "info": ", ".join(cond_infos[:3]) + ("..." if len(cond_infos) > 3 else ""),
                        "params": cond_infos,
                        "is_container": True,
                        "type": "ConditionsGroup",
                        "path": cond_path,
                        "is_active": False,
                    })

        traverse(root, 0)

        # Автоопределение активного элемента
        if not any(n.get("is_active") for n in tree):
            for n in tree:
                if n.get("status") == "running":
                    n["is_active"] = True
                    break

        self.sequence_tree = tree

        # Логирование смены активного элемента
        active_node = next((n for n in tree if n.get("is_active")), None)
        if active_node:
            state_key = f"{active_node['path']}|{active_node.get('info', '')}"
            if state_key != self._last_sequence_state_key:
                self._last_sequence_state_key = state_key
                self.log(f"▶ {active_node['name']} {active_node.get('info', '')}", "INFO")

        return tree

    def get_sequence_dashboard(self) -> Dict[str, Any]:
        """Получение сводной информации о последовательности"""
        data = self._nina_request("sequence/state", "GET", silent_errors=True)
        result = {
            "status": "НЕТ ДАННЫХ", "target": "-", "instruction": "-",
            "progress": "-", "exposure": "-", "is_running": False
        }
        if not data:
            file_path = self.nina_profile.get("sequence", {}).get("startup_template", "")
            if file_path and os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        root = json.load(f)
                    target_name = self._find_target_in_tree(root)
                    result["target"] = target_name or "-"
                    result["status"] = "ОСТАНОВЛЕН (локальный файл)"
                    return result
                except Exception:
                    pass
            return result
        resp = data.get("Response", data)
        target_name = self._find_target_in_tree(resp)
        active_info = self._find_active_instruction(resp)
        is_running = False
        if isinstance(resp, dict):
            st = str(resp.get("State", resp.get("Status", "Unknown"))).lower()
            if "running" in st:
                is_running = True
            if active_info.get("is_running"):
                is_running = True
        result["is_running"] = is_running
        result["status"] = "СЪЁМКА ИДЕТ" if is_running else "ОСТАНОВЛЕН"
        display_target = target_name
        if not display_target or display_target == "-":
            if isinstance(resp, dict):
                root_name = resp.get("Name", "")
                if root_name and "_Container" not in root_name and root_name not in ["Target", "Sequence"]:
                    display_target = root_name
        result["target"] = display_target or "-"
        result["instruction"] = active_info.get("step_name", "-")
        completed = active_info.get("completed", "-")
        total = active_info.get("total", "-")
        result["progress"] = f"{completed} из {total}" if completed != "-" and total != "-" else str(completed)
        exp_time = active_info.get("exposure_time", "-")
        result["exposure"] = f"{exp_time} сек" if exp_time != "-" else "-"
        self.sequence_details = result
        return result

    def _find_target_in_tree(self, node: Any) -> Optional[str]:
        """Поиск имени цели в дереве"""
        if node is None:
            return None
        if isinstance(node, dict):
            target_obj = node.get("Target")
            if isinstance(target_obj, dict):
                for key in ["Name", "ObjectName", "Designation", "TargetName"]:
                    val = target_obj.get(key)
                    if val and isinstance(val, str) and val.strip():
                        clean = val.strip()
                        if "_Container" not in clean and clean not in ["Target", "Unknown"]:
                            return clean
            for key, value in node.items():
                if key in ["Items", "Children", "Targets", "Target", "Triggers", "Containers"]:
                    if isinstance(value, dict) and "$values" in value:
                        result = self._find_target_in_tree(value["$values"])
                    else:
                        result = self._find_target_in_tree(value)
                    if result:
                        return result
        elif isinstance(node, list):
            for item in node:
                result = self._find_target_in_tree(item)
                if result:
                    return result
        return None

    def _find_active_instruction(self, node: Any, path: str = "") -> Dict[str, Any]:
        """Поиск активной инструкции в дереве"""
        result = {"is_running": False, "step_name": "-", "exposure_time": "-",
                  "completed": "-", "total": "-", "path": None}
        if node is None:
            return result
        if isinstance(node, dict):
            status = str(node.get("Status", "")).upper()
            name = str(node.get("Name", "") or node.get("Text", "") or "")
            is_container = "Container" in node.get("$type", "") or "_Container" in name or name in ["Target", "DSO", "Event", "Trigger", "Sequence"]
            current_path = f"{path}/{name}" if path else name
            if status == "RUNNING" and not is_container and name:
                result["is_running"] = True
                result["step_name"] = name
                result["path"] = current_path
                if "ExposureTime" in node:
                    result["exposure_time"] = node["ExposureTime"]
                if "CompletedIterations" in node:
                    result["completed"] = node["CompletedIterations"]
                result["total"] = node.get("Iterations", "-")
                return result
            for key in ["Items", "Children", "Triggers", "Containers"]:
                if key in node:
                    val = node[key]
                    if isinstance(val, dict) and "$values" in val:
                        val = val["$values"]
                    if isinstance(val, list):
                        for item in val:
                            child_result = self._find_active_instruction(item, current_path)
                            if child_result["is_running"]:
                                return child_result
        elif isinstance(node, list):
            for item in node:
                child_result = self._find_active_instruction(item, path)
                if child_result["is_running"]:
                    return child_result
        return result

    # ===================================================================
    # ТЕСТ КОМАНД
    # ===================================================================
    def test_all_commands(self) -> List[Dict]:
        """Тестирование всех endpoints API"""
        results = []
        test_time = datetime.now().strftime("%H:%M:%S")
        self.log(f"[{test_time}] === НАЧАЛО ТЕСТИРОВАНИЯ КОМАНД ===", "INFO")
        safe_endpoints = [
            ("equipment/info", "GET", None, "Общая информация"),
            ("equipment/camera/info", "GET", None, "Камера info"),
            ("equipment/mount/info", "GET", None, "Монтировка info"),
            ("equipment/focuser/info", "GET", None, "Фокусёр info"),
            ("equipment/filterwheel/info", "GET", None, "Колесо фильтров info"),
            ("equipment/guider/info", "GET", None, "Гид info"),
            ("equipment/rotator/info", "GET", None, "Ротатор info"),
            ("equipment/weather/info", "GET", None, "Погода info"),
            ("sequence/state", "GET", None, "Состояние последовательности"),
            ("sequence/json", "GET", None, "JSON последовательности"),
            ("prepared-image/info", "GET", None, "Информация о последнем кадре"),
        ]
        for endpoint, method, data, description in safe_endpoints:
            start = time.time()
            try:
                response = self._nina_request(endpoint, method, data, silent_errors=True, custom_timeout=10)
                duration = round((time.time() - start) * 1000, 1)
                if response is None:
                    status = "OFFLINE"
                    details = "Устройство не подключено"
                elif response.get("Success") is False or response.get("Error"):
                    status = "ERROR"
                    details = response.get("Error") or response.get("Message", "Неизвестная ошибка")
                else:
                    status = "OK"
                    resp_data = response.get("Response", response)
                    if isinstance(resp_data, dict):
                        if "Connected" in resp_data:
                            details = f"Подключено: {resp_data.get('Name', 'Unknown')}" if resp_data["Connected"] else "Отключено"
                        else:
                            details = f"Получено {len(json.dumps(resp_data))} байт"
                    else:
                        details = "Ответ получен"
            except Exception as e:
                duration = round((time.time() - start) * 1000, 1)
                status = "EXCEPTION"
                details = str(e)
            result_entry = {
                "endpoint": endpoint, "method": method, "description": description,
                "status": status, "details": details, "duration_ms": duration,
                "timestamp": datetime.now().isoformat(),
            }
            results.append(result_entry)
            self.log(f"[{description}] {status} ({duration}ms): {details}",
                     "INFO" if status == "OK" else "WARNING")
        try:
            tree = self.build_sequence_tree()
            if tree:
                containers = sum(1 for n in tree if n.get("is_container"))
                results.append({
                    "endpoint": "sequence/parse", "method": "PARSE",
                    "description": "Парсинг дерева последовательности",
                    "status": "OK",
                    "details": f"Узлов: {len(tree)}, контейнеров: {containers}",
                    "duration_ms": 0, "timestamp": datetime.now().isoformat(),
                })
        except Exception as e:
            results.append({
                "endpoint": "sequence/parse", "method": "PARSE",
                "description": "Парсинг дерева последовательности",
                "status": "EXCEPTION", "details": str(e),
                "duration_ms": 0, "timestamp": datetime.now().isoformat(),
            })
        ok_count = sum(1 for r in results if r["status"] == "OK")
        err_count = sum(1 for r in results if r["status"] in ["ERROR", "EXCEPTION"])
        offline_count = sum(1 for r in results if r["status"] == "OFFLINE")
        summary = f"Тест завершён: {ok_count} OK, {offline_count} OFFLINE, {err_count} ERROR из {len(results)}"
        self.log(f"=== ИТОГ: {summary} ===", "INFO")
        self.test_results = results
        self._broadcast({"type": "test_results", "data": results})
        return results

    # ===================================================================
    # ОБРАБОТКА СООБЩЕНИЙ
    # ===================================================================
    def _fix_layout(self, text: str) -> str:
        """Исправление раскладки клавиатуры (EN -> RU)"""
        en_to_ru = {
            'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н', 'u': 'г',
            'i': 'ш', 'o': 'щ', 'p': 'з', '[': 'х', ']': 'ъ', 'a': 'ф', 's': 'ы',
            'd': 'в', 'f': 'а', 'g': 'п', 'h': 'р', 'j': 'о', 'k': 'л', 'l': 'д',
            ';': 'ж', "'": 'э', 'z': 'я', 'x': 'ч', 'c': 'с', 'v': 'м', 'b': 'и',
            'n': 'т', 'm': 'ь', ',': 'б', '.': 'ю', '/': '.', '`': 'ё'
        }
        if not any('\u0400' <= c <= '\u04FF' for c in text):
            return "".join([en_to_ru.get(c.lower(), c).upper() if c.isupper()
                           else en_to_ru.get(c.lower(), c) for c in text])
        return text

    def _is_question(self, message: str) -> bool:
        """Определение, является ли сообщение вопросом"""
        msg_lower = message.lower().strip()
        if '?' in message:
            return True
        for pattern in self.question_patterns:
            if re.search(pattern, msg_lower):
                return True
        return False

    def process_message(self, message: str):
        """Обработка входящего сообщения"""
        try:
            current_mode = self.ai_mode
            is_question = self._is_question(message)
            if current_mode == "auto":
                if is_question:
                    self._handle_consultant_mode(message)
                else:
                    self._handle_command_mode(message)
            elif current_mode == "command":
                self._handle_command_mode(message)
            elif current_mode == "consultant":
                self._handle_consultant_mode(message)
        except Exception as e:
            self.log(f"Ошибка обработки: {str(e)}", "ERROR")
            self.add_to_chat("AI", f"Ошибка: {str(e)}")
            self.update_ai_status(False)

    def _handle_command_mode(self, message: str):
        """Обработка в режиме команд"""
        self.update_ai_status(True)
        try:
            commands = self._parse_commands(message)
            if not commands:
                fixed_message = self._fix_layout(message)
                if fixed_message != message:
                    commands = self._parse_commands(fixed_message)
            if not commands:
                ai_response = self._ask_ollama(message, mode="executor")
                if isinstance(ai_response, dict):
                    if ai_response.get("type") == "command":
                        commands = [ai_response]
                    elif ai_response.get("type") == "command_chain":
                        commands = ai_response.get("commands", [])
                    elif ai_response.get("type") == "chat":
                        self.add_to_chat("AI", ai_response.get("message", ""))
                        return
            if commands:
                self._execute_command_chain(commands)
            else:
                self.add_to_chat("Система", "Команда не распознана")
        finally:
            self.update_ai_status(False)

    def _handle_consultant_mode(self, message: str):
        """Обработка в режиме консультанта"""
        self.update_ai_status(True)
        try:
            ai_response = self._ask_ollama(message, mode="consultant")
            if isinstance(ai_response, dict):
                msg_type = ai_response.get("type", "chat")
                if msg_type == "chat":
                    self.add_to_chat("AI", ai_response.get("message", ""))
                elif msg_type in ["command", "command_chain"]:
                    commands = [ai_response] if msg_type == "command" else ai_response.get("commands", [])
                    self._execute_command_chain(commands)
        finally:
            self.update_ai_status(False)

    def _parse_commands(self, message: str) -> List[Dict[str, Any]]:
        """Парсинг текстовых команд"""
        msg = message.lower().strip()
        commands = []
        if "стоп всё" in msg or "аварийн" in msg:
            return [{"action": "emergency_stop", "params": {}}]
        if ("подключ" in msg or "включ" in msg) and ("всё" in msg or "все" in msg):
            commands.append({"action": "connect_all", "params": {}})
        elif "подключ" in msg or "включ" in msg:
            if "камер" in msg: commands.append({"action": "connect_camera", "params": {}})
            if "фокус" in msg: commands.append({"action": "connect_focuser", "params": {}})
            if "монт" in msg: commands.append({"action": "connect_mount", "params": {}})
            if "гид" in msg: commands.append({"action": "connect_guider", "params": {}})
            if "фильтр" in msg: commands.append({"action": "connect_filterwheel", "params": {}})
        if ("отключ" in msg or "выключ" in msg) and ("всё" in msg or "все" in msg):
            commands.append({"action": "disconnect_all", "params": {}})
        cool_match = self.re_cool.search(msg)
        if cool_match:
            commands.append({"action": "cool", "params": {"temperature": int(cool_match.group(1))}})
        if "нагрей" in msg:
            commands.append({"action": "warm_up", "params": {}})
        dso_found = None
        sorted_aliases = sorted(self.dso_aliases.keys(), key=len, reverse=True)
        for alias in sorted_aliases:
            if len(alias) > 2 and (alias in msg or msg in alias):
                dso_found = self.dso_aliases[alias]
                break
        if dso_found:
            commands.append({"action": "slew_object", "params": {"object": dso_found}})
        if "парк" in msg and "рас" not in msg:
            commands.append({"action": "park", "params": {}})
        if "распарк" in msg:
            commands.append({"action": "unpark", "params": {}})
        if "домой" in msg:
            commands.append({"action": "home_mount", "params": {}})
        if "звёздн" in msg and "скорост" in msg:
            commands.append({"action": "set_tracking_rate", "params": {"rate": "sidereal"}})
        if "лунн" in msg and "скорост" in msg:
            commands.append({"action": "set_tracking_rate", "params": {"rate": "lunar"}})
        if "фильтр" in msg:
            for f in self.equipment_registry.get("Filters", []):
                if f.lower() in msg:
                    commands.append({"action": "set_filter", "params": {"filter": f}})
                    break
        if "автофокус" in msg:
            commands.append({"action": "autofocus", "params": {}})
        if "platesolve" in msg:
            commands.append({"action": "platesolve", "params": {}})
        if ("запуст" in msg or "старт" in msg) and "гид" in msg:
            commands.append({"action": "start_guide", "params": {}})
        if ("останов" in msg or "стоп" in msg) and "гид" in msg:
            commands.append({"action": "stop_guide", "params": {}})
        if "дизеринг" in msg or "dither" in msg:
            commands.append({"action": "dither_on", "params": {}})
        if "калибр" in msg and "гид" in msg:
            commands.append({"action": "calibrate_guide", "params": {}})
        if ("запуст" in msg or "старт" in msg) and "секвен" in msg:
            commands.append({"action": "start_seq", "params": {}})
        if ("останов" in msg or "стоп" in msg) and "секвен" in msg:
            commands.append({"action": "stop_seq", "params": {}})
        if "пропусти" in msg:
            commands.append({"action": "advance_seq", "params": {}})
        if "сброс" in msg and "секвен" in msg:
            commands.append({"action": "reset_seq", "params": {}})
        explicit_duration = None
        for p in [r'по\s+(\d+)\s*[ссек]', r'на\s+(\d+)\s*[ссек]', r'(\d+)\s*(?:секунд|сек|с)\b']:
            m = re.search(p, msg, re.IGNORECASE)
            if m:
                explicit_duration = int(m.group(1))
                break
        snap_match = self.re_snap.search(msg)
        if explicit_duration is None and snap_match:
            explicit_duration = int(snap_match.group(1))
        series_match = self.re_series.search(msg)
        if series_match:
            params = self._get_current_camera_params()
            params["count"] = int(series_match.group(1))
            if explicit_duration:
                params["duration"] = explicit_duration
            commands.append({"action": "series", "params": params})
        elif explicit_duration:
            params = self._get_current_camera_params()
            params["duration"] = explicit_duration
            commands.append({"action": "exposure", "params": params})
        unique = []
        seen = set()
        for cmd in commands:
            cmd_str = json.dumps(cmd, sort_keys=True)
            if cmd_str not in seen:
                seen.add(cmd_str)
                unique.append(cmd)
        return unique

    def _get_current_camera_params(self) -> Dict[str, Any]:
        """Получение текущих параметров камеры"""
        gain = 85
        offset = 10
        cam_tel = self.detailed_telemetry.get("camera", {})
        if cam_tel.get("gain") is not None:
            try: gain = int(cam_tel["gain"])
            except: pass
        if cam_tel.get("offset") is not None:
            try: offset = int(cam_tel["offset"])
            except: pass
        return {"duration": 30.0, "gain": gain, "offset": offset}

    def _execute_command_chain(self, commands: List[Dict[str, Any]]):
        """Выполнение цепочки команд"""
        total = len(commands)
        for i, cmd in enumerate(commands):
            action = cmd.get("action", "unknown")
            self.log(f"Цепочка [{i+1}/{total}]: {action}", "INFO")
            result = self._execute_command(cmd)
            self.add_to_chat("Система", f"[{i+1}/{total}] {action} → {result}")
            if action in ["connect_all", "disconnect_all"]:
                time.sleep(3.0)
            elif action.startswith("connect_"):
                time.sleep(1.5)
            elif action in ["slew_object", "park", "unpark", "home_mount"]:
                self._wait_for_mount_idle()
            elif action == "exposure":
                self._wait_for_camera_idle()
            else:
                time.sleep(0.5)

    def _execute_command(self, command: Dict[str, Any]) -> str:
        """Выполнение одной команды"""
        action = str(command.get("action", "")).strip().replace(" ", "_").lower()
        params = command.get("params", {})
        try:
            if action == "connect_all":
                for dev in ["camera", "mount", "filterwheel", "focuser", "guider", "rotator", "weather"]:
                    self._nina_request(f"equipment/{dev}/connect", "GET")
                return "Подключение отправлено"
            elif action.startswith("connect_") and action != "connect_all":
                dev = action.replace("connect_", "")
                self._nina_request(f"equipment/{dev}/connect", "GET")
                return f"Подключено: {dev}"
            elif action == "disconnect_all":
                for dev in ["camera", "mount", "filterwheel", "focuser", "guider", "rotator", "weather"]:
                    self._nina_request(f"equipment/{dev}/disconnect", "GET", silent_errors=True)
                return "Отключение отправлено"
            elif action == "apply_camera_params":
                gain = params.get("gain")
                offset = params.get("offset")
                results = []
                if gain is not None:
                    self._nina_request("profile/change-value", "GET",
                                       {"settingpath": "CameraSettings-Gain", "newValue": str(gain)})
                    results.append(f"Gain={gain}")
                if offset is not None:
                    self._nina_request("profile/change-value", "GET",
                                       {"settingpath": "CameraSettings-Offset", "newValue": str(offset)})
                    results.append(f"Offset={offset}")
                return f"{', '.join(results)} установлены"
            elif action == "exposure":
                duration = params.get("duration", 10)
                query = {"duration": duration, "waitForResult": "true"}
                if params.get("gain"):
                    query["gain"] = params["gain"]
                result = self._nina_request("equipment/camera/capture", "GET", query)
                return f"Снимок {duration}с завершен" if result else "Не удалось"
            elif action == "series":
                count = int(params.get("count", 1))
                duration = float(params.get("duration", 10))
                gain = params.get("gain")
                for i in range(count):
                    if not self.is_running: break
                    self.log(f"Кадр {i+1}/{count}: {duration}с...", "INFO")
                    query = {"duration": duration, "waitForResult": "true"}
                    if gain: query["gain"] = gain
                    self._nina_request("equipment/camera/capture", "GET", query)
                    if i < count - 1: time.sleep(1.0)
                return f"Серия: {count} x {duration}с"
            elif action == "abort_capture":
                self._nina_request("equipment/camera/abort-exposure", "GET", silent_errors=True)
                self._nina_request("sequence/stop", "GET", silent_errors=True)
                return "Съёмка прервана"
            elif action == "cool":
                self._nina_request("equipment/camera/cool", "GET", {"temperature": params["temperature"]})
                return f"Охлаждение: {params['temperature']}°C"
            elif action == "warm_up":
                self._nina_request("equipment/camera/warm", "GET")
                return "Нагрев"
            elif action == "slew_coords":
                ra = params["ra"]
                dec = params["dec"]
                if self.settings.get("coord_units", "degrees") == "degrees":
                    ra = ra / 15.0
                self._nina_request("equipment/mount/slew", "GET", {"ra": ra, "dec": dec})
                return f"Наведение: RA={ra:.4f}h, Dec={dec}°"
            elif action == "stop_slew":
                self._nina_request("equipment/mount/slew/stop", "GET")
                return "Остановлено"
            elif action == "park":
                self._nina_request("equipment/mount/park", "GET")
                return "Парковка"
            elif action == "unpark":
                self._nina_request("equipment/mount/unpark", "GET")
                return "Распарковка"
            elif action == "home_mount":
                self._nina_request("equipment/mount/home", "GET")
                return "Домой"
            elif action == "set_tracking_rate":
                rate = params.get("rate", "sidereal")
                rate_map = {"sidereal": 0, "lunar": 1, "solar": 2, "king": 3, "stop": 5}
                rate_names_ru = {"sidereal": "звёздная", "lunar": "лунная", "solar": "солнечная", "king": "King", "stop": "стоп"}
                rate_id = rate_map.get(rate, 0)
                result = self._nina_request("equipment/mount/tracking", "GET",
                                           {"trackingMode": rate_id}, silent_errors=True)
                rate_name = rate_names_ru.get(rate, rate)
                return f"Скорость: {rate_name}" if result else f"Не удалось ({rate_name})"
            elif action == "autofocus":
                self._nina_request("equipment/focuser/auto-focus", "GET")
                return "Автофокус запущен"
            elif action == "move_focuser":
                steps = params.get("steps", 0)
                status = self._nina_request("equipment/focuser/info", silent_errors=True)
                if status:
                    info = status.get("Response", status)
                    current = info.get("Position", 0)
                    target = current + steps
                    self._nina_request("equipment/focuser/move", "GET", {"position": target})
                    return f"Сдвиг на {steps} (в {target})"
                return "Позиция недоступна"
            elif action == "move_focuser_abs":
                self._nina_request("equipment/focuser/move", "GET", {"position": params["position"]})
                return f"Переход в {params['position']}"
            elif action == "start_guide":
                self._nina_request("equipment/guider/start", "GET")
                return "Гид запущен"
            elif action == "stop_guide":
                self._nina_request("equipment/guider/stop", "GET")
                return "Гид остановлен"
            elif action == "dither_on":
                self._nina_request("equipment/guider/dither", "GET")
                return "Дизеринг"
            elif action == "calibrate_guide":
                self._nina_request("equipment/guider/clear-calibration", "GET")
                return "Калибровка сброшена"
            elif action == "set_filter":
                filter_name = params["filter"]
                filter_id = self.equipment_registry.get("FilterMap", {}).get(filter_name)
                if filter_id is not None:
                    self._nina_request("equipment/filterwheel/change-filter", "GET", {"filterId": filter_id})
                    return f"Фильтр: {filter_name}"
                return f"Фильтр {filter_name} не найден"
            elif action == "start_seq":
                result = self._nina_request("sequence/start", "GET")
                return "Последовательность запущена" if result else "Ошибка"
            elif action == "stop_seq":
                result = self._nina_request("sequence/stop", "GET")
                return "Последовательность остановлена" if result else "Ошибка"
            elif action == "advance_seq":
                result = self._nina_request("sequence/skip", "GET", data={"type": "CurrentItems"})
                return "Этап пропущен" if result else "Ошибка"
            elif action == "reset_seq":
                self._nina_request("sequence/stop", "GET", silent_errors=True)
                time.sleep(1.5)
                result = self._nina_request("sequence/reset", "GET")
                return "Сброшена" if result else "Ошибка"
            elif action == "rotator_move":
                self._nina_request("equipment/rotator/move", "GET", {"position": params["position"]})
                return f"Ротатор: {params['position']}°"
            elif action == "slew_object":
                obj_key = params.get("object", "").strip().lower()
                target_data = None
                if obj_key in self.dso_catalog:
                    target_data = self.dso_catalog[obj_key]
                elif obj_key in self.dso_aliases:
                    target_data = self.dso_catalog.get(self.dso_aliases[obj_key])
                if target_data:
                    self._nina_request("equipment/mount/slew", "GET",
                                       {"ra": target_data.get("ra"), "dec": target_data.get("dec")})
                    return f"Наведение на {obj_key.upper()}"
                return f"Объект '{obj_key}' не найден"
            elif action == "platesolve":
                self._nina_request("prepared-image/solve", "GET")
                return "Platesolve запущен"
            elif action == "emergency_stop":
                self._nina_request("sequence/stop", "GET", silent_errors=True)
                self._nina_request("equipment/camera/abort-exposure", "GET", silent_errors=True)
                self._nina_request("equipment/guider/stop", "GET", silent_errors=True)
                self._nina_request("equipment/mount/park", "GET", silent_errors=True)
                return "АВАРИЙНЫЙ СТОП!"
            return "OK"
        except Exception as e:
            return f"Ошибка: {str(e)}"

    # ===================================================================
    # 🚀 ОПТИМИЗИРОВАННАЯ ЛОГИКА AI (3 промта + дайджест + retry + fallback)
    # ===================================================================

    def _build_compact_digest(self) -> str:
        """
        Компактный дайджест ВСЕХ метрик системы для AI.
        Вместо больших JSON контекстов используется текстовый дайджест ~1500 символов.
        """
        lines = ["=== ДАЙДЖЕСТ СИСТЕМЫ ==="]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"Время: {now}")

        # Подключение
        lines.append(f"NINA: {'ON' if self.nina_connected else 'OFF'} | Ollama: {'ON' if self.ollama_connected else 'OFF'} | Модель: {self.model}")

        # Оборудование
        if self.nina_connected:
            tel = self.detailed_telemetry
            # Камера
            cam = tel.get("camera", {})
            if cam:
                lines.append(f"КАМЕРА: {cam.get('name','-')} | T={cam.get('temperature','-')}°C (цель {cam.get('target_temp','-')}°C) | Кулер={'ON' if cam.get('cooler_on') else 'OFF'} {round(float(cam.get('cooler_power') or 0)*100)}% | Эксп={'YES' if cam.get('is_exposing') else 'NO'} | G={cam.get('gain','-')} O={cam.get('offset','-')}")
            # Монтировка
            mnt = tel.get("mount", {})
            if mnt:
                lines.append(f"МОНТИРОВКА: {mnt.get('name','-')} | RA={mnt.get('right_ascension','-')}h Dec={mnt.get('declination','-')}° | Парк={'YES' if mnt.get('parked') else 'NO'} | Ведение={'ON' if mnt.get('tracking') else 'OFF'} {mnt.get('tracking_mode','-')} | Slew={'YES' if mnt.get('slewing') else 'NO'}")
            # Фокусёр
            foc = tel.get("focuser", {})
            if foc:
                lines.append(f"ФОКУСЁР: {foc.get('name','-')} | Pos={foc.get('position','-')} | T={foc.get('temperature','-')}°C | Moving={'YES' if foc.get('moving') else 'NO'}")
            # Фильтры
            flt = tel.get("filters", {})
            if flt:
                sel = flt.get("selected_filter")
                sel_name = sel.get("Name") if isinstance(sel, dict) else sel
                lines.append(f"ФИЛЬТРЫ: {flt.get('name','-')} | Текущий={sel_name or 'нет'} | Всего={flt.get('filter_count', 0)}")
            # Ротатор
            rot = tel.get("rotator", {})
            if rot:
                lines.append(f"РОТАТОР: {rot.get('name','-')} | Pos={rot.get('position','-')}°")

        # Гид
        g = self.guider_details or {}
        unit = g.get("unit", "arcsec")
        lines.append(f"ГИД: Активен={'YES' if g.get('is_guiding') else 'NO'} | RMS Total={g.get('rms_total','-')} {unit} | RA={g.get('rms_ra','-')} Dec={g.get('rms_dec','-')} | Scale={g.get('pixel_scale','-')}\"/px")

        # Среда
        env = self.environment_data or {}
        if env.get("source") != "unknown":
            lines.append(f"СРЕДА ({env.get('source','-')}): T={env.get('temperature','-')}°C | Влаж={env.get('humidity','-')}% | Облач={env.get('cloud_cover','-')}% | Ветер={env.get('wind_speed','-')}м/с | Давл={env.get('pressure','-')}hPa | Безопасно={'YES' if env.get('safe') else 'NO'}")

        # Последовательность
        seq = self.sequence_details or {}
        lines.append(f"ПОСЛЕДОВАТЕЛЬНОСТЬ: {seq.get('status','НЕТ ДАННЫХ')} | Цель={seq.get('target','-')} | Этап={seq.get('instruction','-')} | Прогресс={seq.get('progress','-')} | Эксп={seq.get('exposure','-')}")

        # Статистика кадра
        img = self.image_stats or {}
        if img:
            lines.append(f"ПОСЛЕДНИЙ КАДР: HFR={img.get('hfr','-')}px | FWHM={img.get('fwhm','-')}px | Звёзд={img.get('stars','-')} | Mean={img.get('mean','-')} | Exp={img.get('exposure','-')}с | Filter={img.get('filter','-')}")

        # Сессия
        ss = self.session_stats or {}
        if ss.get("total_frames"):
            exp_h = ss.get("total_exposure_time", 0) / 3600
            lines.append(f"СЕССИЯ: Кадров={ss.get('total_frames',0)} | Выдержка={exp_h:.1f}ч | Avg HFR={ss.get('avg_hfr',0):.2f} | Best={ss.get('best_hfr','-')} | Worst={ss.get('worst_hfr','-')}")

        # Session Metadata
        sm = self.session_metadata.get_session_summary()
        if sm.get("total_frames"):
            hfr_s = sm.get("hfr_stats", {})
            lines.append(f"METADATA: Кадров={sm.get('total_frames')} | {sm.get('total_exposure_formatted','')} | Avg HFR={hfr_s.get('avg','-')} | Min={hfr_s.get('min','-')} | Max={hfr_s.get('max','-')}")
            by_f = sm.get("by_filter", {})
            if by_f:
                filters_str = ", ".join(f"{f}:{d['count']}" for f, d in by_f.items())
                lines.append(f"ПО ФИЛЬТРАМ: {filters_str}")

        # Профиль
        p = self.nina_profile or {}
        if p.get("name"):
            cam_p = p.get("camera", {})
            tel_p = p.get("telescope", {})
            lines.append(f"ОБОРУДОВАНИЕ: {p.get('name','-')} | Телескоп: {tel_p.get('name','-')} {tel_p.get('focal_length','-')}мм f/{tel_p.get('focal_ratio','-')} | Камера: {cam_p.get('device_name','-')} {cam_p.get('pixel_size','-')}мкм | Монтировка: {tel_p.get('mount_name','-')}")

        # Prometheus сводка
        snap = self.prometheus.snapshot()
        api_req = snap.get("nina_api_requests_total")
        api_err = 0
        if isinstance(api_req, dict):
            api_req = sum(api_req.values()) if api_req else 0
        api_err_dict = snap.get("nina_api_errors_total")
        if isinstance(api_err_dict, dict):
            api_err = sum(api_err_dict.values()) if api_err_dict else 0
        if api_req:
            lines.append(f"API: Запросов={int(api_req)} | Ошибок={int(api_err)} | AI={int(snap.get('nina_ai_requests_total', 0))} (err {int(snap.get('nina_ai_errors_total', 0))})")

        return "\n".join(lines)

    def _build_chat_context(self) -> str:
        """Построение контекста чата"""
        if not self.chat_history:
            return "История диалога пуста."
        recent = self.chat_history[-self.max_chat_history:]
        lines = ["ИСТОРИЯ ДИАЛОГА:"]
        for msg in recent:
            lines.append(f"[{msg.get('time', '?')}] {msg.get('sender', '?')}: {msg.get('message', '')[:200]}")
        return "\n".join(lines)

    def _ask_ollama(self, message: str, mode: str = "executor") -> Dict[str, Any]:
        """Отправка запроса к Ollama с retry при пустом ответе"""
        try:
            if not self.ollama_connected:
                return {"type": "chat", "message": "Ollama не подключен"}

            # Формируем компактный дайджест (один для всех режимов)
            digest = self._build_compact_digest()
            chat_ctx = self._build_chat_context()

            system_prompt = self._build_system_prompt(mode, digest, chat_ctx)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ]
            data = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.3 if mode == "executor" else 0.7,
                    "top_p": 0.9,
                    "num_ctx": 8192,
                    "num_predict": 1500
                }
            }

            self.log(f"AI запрос ({mode}, {len(system_prompt)} символов промт)", "DEBUG")

            # Попытки с retry
            last_text = ""
            for attempt in range(3):
                try:
                    response = requests.post(f"{self.ollama_url}/api/chat", json=data, timeout=180)
                    if response.status_code == 200:
                        resp_data = response.json()
                        text = resp_data.get("message", {}).get("content", "")
                        last_text = text
                        self.log(f"AI ответ (попытка {attempt+1}, {len(text)} симв)", "DEBUG")
                        if not text or text.strip() == "":
                            self.log(f"AI пустой ответ, retry {attempt+1}/3", "WARNING")
                            time.sleep(1)
                            continue
                        parsed = self._extract_json(text)
                        if parsed and isinstance(parsed, dict) and "type" in parsed:
                            return parsed
                        # Fallback - пробуем распарсить команду из текста
                        fallback = self._fallback_parse(message, text)
                        if fallback:
                            return fallback
                        return {"type": "chat", "message": text}
                except requests.exceptions.Timeout:
                    self.log(f"AI timeout, retry {attempt+1}/3", "WARNING")
                    if attempt < 2:
                        time.sleep(2)
                except Exception as e:
                    self.log(f"AI error: {e}", "WARNING")
                    break

            # Последняя попытка без format:json
            self.log("Последняя попытка без format:json", "DEBUG")
            try:
                data_noformat = dict(data)
                data_noformat.pop("format", None)
                response = requests.post(f"{self.ollama_url}/api/chat", json=data_noformat, timeout=240)
                if response.status_code == 200:
                    text = response.json().get("message", {}).get("content", "")
                    last_text = text
                    if text:
                        parsed = self._extract_json(text)
                        if parsed:
                            return parsed
                        fallback = self._fallback_parse(message, text)
                        if fallback:
                            return fallback
                        return {"type": "chat", "message": text}
            except Exception as e:
                self.log(f"AI final attempt failed: {e}", "ERROR")

            self.ai_errors_count += 1
            return {"type": "chat", "message": last_text[:500] if last_text else "Не удалось получить ответ от AI. Попробуйте переформулировать или проверьте Ollama."}
        except Exception as e:
            self.ai_errors_count += 1
            return {"type": "chat", "message": f"Ошибка AI: {str(e)}"}

    def _extract_json(self, text: str) -> Optional[Dict]:
        """Извлечение JSON из текста ответа"""
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            text = match.group(1)
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(text[start:end+1])
                if isinstance(parsed, dict) and "type" in parsed:
                    return parsed
            except Exception:
                pass
        return None

    def _fallback_parse(self, user_msg: str, ai_text: str) -> Optional[Dict]:
        """Fallback-парсер: если AI вернул текст, пытаемся извлечь из него команду"""
        text = ai_text.lower()
        # Поиск упоминания известных команд
        known_actions = [
            "connect_all", "disconnect_all", "emergency_stop",
            "connect_camera", "connect_mount", "connect_focuser", "connect_guider", "connect_filterwheel",
            "exposure", "series", "abort_capture", "cool", "warm_up", "apply_camera_params",
            "slew_object", "slew_coords", "park", "unpark", "stop_slew", "home_mount",
            "set_tracking_rate", "platesolve",
            "autofocus", "move_focuser", "move_focuser_abs",
            "start_guide", "stop_guide", "dither_on", "calibrate_guide",
            "start_seq", "stop_seq", "advance_seq", "reset_seq",
            "set_filter", "rotator_move"
        ]
        for action in known_actions:
            if action in text:
                self.log(f"Fallback: извлечена команда {action}", "DEBUG")
                return {"type": "command", "action": action, "params": {}}
        return None

    def _build_system_prompt(self, mode: str, digest: str, chat_ctx: str) -> str:
        """Построение промта в зависимости от режима"""
        if mode == "command":
            return self._build_command_prompt(digest, chat_ctx)
        elif mode == "consultant":
            return self._build_consultant_prompt(digest, chat_ctx)
        else:
            return self._build_auto_prompt(digest, chat_ctx)

    def _build_command_prompt(self, digest: str, chat_ctx: str) -> str:
        """Промт для режима 'command' - строгий исполнитель"""
        return f"""Ты - ИСПОЛНИТЕЛЬ КОМАНД для астрофотографического комплекса N.I.N.A.
Твоя задача: преобразовать запрос пользователя в JSON-команду или цепочку команд.
Отвечай СТРОГО JSON. Никаких пояснений вне JSON.

{digest}

{chat_ctx}

=== ПОЛНЫЙ СПИСОК КОМАНД (action) ===

[ОБОРУДОВАНИЕ]
connect_all (params: {{}}) - подключить всё
disconnect_all (params: {{}}) - отключить всё
emergency_stop (params: {{}}) - аварийный стоп всего
connect_camera / connect_mount / connect_focuser / connect_guider / connect_filterwheel (params: {{}})

[КАМЕРА]
exposure (params: {{"duration": float_сек, "gain": int, "offset": int}}) - один кадр
series (params: {{"count": int, "duration": float, "gain": int, "offset": int}}) - серия кадров
abort_capture (params: {{}}) - прервать съёмку
cool (params: {{"temperature": int_°C}}) - охладить
warm_up (params: {{}}) - нагреть
apply_camera_params (params: {{"gain": int, "offset": int}})

[МОНТИРОВКА]
slew_object (params: {{"object": "M31"}}) - наведение на объект из каталога
slew_coords (params: {{"ra": float_часы, "dec": float_градусы}})
park / unpark / stop_slew / home_mount (params: {{}})
set_tracking_rate (params: {{"rate": "sidereal"|"lunar"|"solar"|"king"|"stop"}})
platesolve (params: {{}})

[ФОКУС]
autofocus (params: {{}})
move_focuser (params: {{"steps": int}}) - сдвиг относительно
move_focuser_abs (params: {{"position": int}}) - абсолютная позиция

[ГИД]
start_guide / stop_guide / dither_on / calibrate_guide (params: {{}})

[ПОСЛЕДОВАТЕЛЬНОСТЬ]
start_seq / stop_seq / advance_seq / reset_seq (params: {{}})

[ПРОЧЕЕ]
set_filter (params: {{"filter": "имя_фильтра"}})
rotator_move (params: {{"position": float_градусы}})

=== ПРАВИЛА ===
1. Отвечай ТОЛЬКО валидным JSON. БЕЗ markdown, БЕЗ комментариев.
2. Если пользователь назвал объект (M31, Туманность Ориона и т.д.) - используй slew_object.
3. Если координаты в градусах - переведи RA в часы (дели на 15).
4. Если команда не распознана - верни {{"type": "chat", "message": "уточнение"}}.
5. НИКОГДА не используй эмодзи.

=== ФОРМАТЫ ОТВЕТА ===
Одна команда: {{"type": "command", "action": "имя", "params": {{...}}}}
Цепочка: {{"type": "command_chain", "commands": [{{"action": "...", "params": {{...}}}}, ...]}}
Уточнение: {{"type": "chat", "message": "текст"}}
"""

    def _build_consultant_prompt(self, digest: str, chat_ctx: str) -> str:
        """Промт для режима 'consultant' - эксперт-консультант"""
        return f"""Ты - ПРОФЕССИОНАЛЬНЫЙ ЭКСПЕРТ-АСТРОФОТОГРАФ и консультант по системе N.I.N.A.
Твоя задача: давать глубокие, профессиональные советы и анализы на основе ВСЕХ доступных метрик.

{digest}

{chat_ctx}

=== ТВОИ ЗНАНИЯ ===
- HFR (Half-Flux Radius): норма 1.5-3.0 px. Если > 3.5 - проблема с фокусом/seeing.
- FWHM = HFR * 2.355. Норма < 5 px для любительских телескопов.
- RMS гида: < 1.0" отлично, 1-2" приемлемо, > 2" плохо.
- Температура камеры: цель -15...-20°C для охлаждения сенсора. Отклонение > 2°C - проблема.
- Мощность кулера 100% длительное время - камера не может охладиться (жарко/пыль).
- Облачность > 50% - снимать не рекомендуется.
- Ветер > 5 м/с - вибрации, плохое качество.
- Seeing (атмосферная турбулентность) - главная причина плохого HFR.
- Меридиан-флип: делать при пересечении меридиана, после - повторный platesolve и АФ.
- Дизеринг: каждые 3-5 кадров для устранения паттернов шума.

=== ПРАВИЛА ОТВЕТА ===
1. Анализируй ВСЕ метрики из дайджеста комплексно.
2. Сравнивай текущие значения с нормами.
3. Выявляй проблемы и предлагай конкретные решения.
4. Предлагай улучшения для текущей сессии.
5. Отвечай на русском языке, подробно, профессионально.
6. Структурируй ответ: Анализ / Проблемы / Рекомендации.
7. НИКОГДА не используй эмодзи.
8. Если видишь проблемы с оборудованием - предлагай команды для исправления через suggested_action.
9. Будь проактивен: предлагай улучшения даже если пользователь не спрашивает.

=== ФОРМАТ ОТВЕТА (СТРОГО JSON) ===
{{"type": "chat", "message": "подробный анализ и рекомендации"}}

Или если нужно предложить команду:
{{"type": "suggestion", "message": "объяснение", "suggested_action": "описание что сделать"}}
"""

    def _build_auto_prompt(self, digest: str, chat_ctx: str) -> str:
        """Промт для режима 'auto' - гибридный (умная маршрутизация)"""
        return f"""Ты - AI-ассистент для астрофотографического комплекса N.I.N.A.
Режим АВТО: сам решаешь, выполнять команду или отвечать на вопрос.

{digest}

{chat_ctx}

=== ПРАВИЛА МАРШРУТИЗАЦИИ ===
1. Если запрос - это команда ("сделай", "включи", "наведи", "стоп" и т.д.) - выполни её.
2. Если запрос - это вопрос ("что", "как", "почему", "какое состояние") - ответь как консультант.
3. Если не уверен - задай уточняющий вопрос.

=== КОМАНДЫ (action) ===
connect_all, disconnect_all, emergency_stop,
connect_camera/mount/focuser/guider/filterwheel,
exposure (duration, gain, offset), series (count, duration, gain, offset), abort_capture,
cool (temperature), warm_up, apply_camera_params (gain, offset),
slew_object (object), slew_coords (ra часы, dec градусы), park, unpark, stop_slew, home_mount,
set_tracking_rate (rate: sidereal/lunar/solar/king/stop), platesolve,
autofocus, move_focuser (steps), move_focuser_abs (position),
start_guide, stop_guide, dither_on, calibrate_guide,
start_seq, stop_seq, advance_seq, reset_seq,
set_filter (filter), rotator_move (position)

=== НОРМЫ ===
- HFR: 1.5-3.0 px норма
- RMS гида: <1.0" отлично, 1-2" приемлемо
- Температура камеры: цель -15...-20°C

=== ФОРМАТЫ ОТВЕТА (СТРОГО JSON, БЕЗ markdown) ===
Команда: {{"type": "command", "action": "имя", "params": {{...}}}}
Цепочка: {{"type": "command_chain", "commands": [...]}}
Ответ: {{"type": "chat", "message": "текст"}}
Совет: {{"type": "suggestion", "message": "объяснение", "suggested_action": "описание"}}

Отвечай ТОЛЬКО JSON. Без эмодзи. На русском языке.
"""

    def set_ai_mode(self, mode: str):
        """Установка режима работы AI"""
        if mode in ["auto", "command", "consultant"]:
            self.ai_mode = mode
            self.log(f"Режим AI: {mode}", "INFO")

    def clear_chat(self):
        """Очистка истории чата"""
        self.chat_history.clear()
        self._broadcast({"type": "chat_clear", "data": {}})

    def clear_log(self):
        """Очистка истории логов"""
        self.log_history.clear()
        self._broadcast({"type": "log_clear", "data": {}})

    def get_current_state(self) -> Dict[str, Any]:
        """Получение полного текущего состояния системы"""
        return sanitize_for_json({
            "chat_history": self.chat_history,
            "log_history": self.log_history[-100:],
            "equipment": {
                "registry": self.equipment_registry,
                "nina_connected": self.nina_connected,
                "ollama_connected": self.ollama_connected,
                "model": self.model,
                "host": self.nina_host,
                "port": self.nina_port,
                "ollama_url": self.ollama_url
            },
            "detailed_telemetry": self.detailed_telemetry,
            "nina_profile": self.nina_profile,
            "image_stats": self.image_stats,
            "session_stats": self.session_stats,
            "image_history": self.image_history[-50:],
            "environment": self.environment_data,
            "guider_details": self.guider_details,
            "focuser_ambient_temp": self.focuser_ambient_temp,
            "sequence_tree": self.sequence_tree,
            "sequence_details": self.sequence_details,
            "test_results": self.test_results,
            "ai_status": {
                "thinking": self.is_ai_thinking,
                "last_response": self.last_ai_response_time.isoformat() if self.last_ai_response_time else None,
                "requests_count": self.ai_requests_count,
                "errors_count": self.ai_errors_count,
                "success_count": self.ai_success_count,
                "mode": self.ai_mode
            },
            "settings": self.settings,
            "available_models": self.available_models,
            "dso_catalog": self.dso_catalog,
            "prometheus": {
                "snapshot": self.prometheus.snapshot(),
                "history": self.prometheus.get_history(60),
            },
            "session_metadata": self.session_metadata.get_session_summary(),
        })


# =====================================================================
# FASTAPI APPLICATION
# =====================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения"""
    await manager.start_broadcast_loop()
    logger.info("Broadcast loop запущен")
    yield
    logger.info("Завершение работы...")
    backend.is_running = False


app = FastAPI(title="NINA AI Assistant Web", lifespan=lifespan)
manager = ConnectionManager()
backend = NinaBackend(broadcast_callback=manager.enqueue)


# =====================================================================
# HTTP ENDPOINTS
# =====================================================================
@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Главная страница"""
    html_path = Path(__file__).parent / "web_ui.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>web_ui.html not found</h1>")


@app.get("/api/state")
async def get_state():
    """Получение полного состояния системы"""
    return backend.get_current_state()


@app.get("/api/settings")
async def get_settings():
    """Получение настроек"""
    return sanitize_for_json({
        "settings": backend.settings,
        "available_models": backend.available_models,
        "connection_info": {
            "nina_host": backend.nina_host,
            "nina_port": backend.nina_port,
            "ollama_url": backend.ollama_url,
            "nina_connected": backend.nina_connected,
            "ollama_connected": backend.ollama_connected
        }
    })


@app.post("/api/settings")
async def update_settings(request: SettingsRequest):
    """Обновление настроек"""
    try:
        settings = request.settings
        if "host" in settings: backend.nina_host = settings["host"]
        if "port" in settings: backend.nina_port = int(settings["port"])
        if "ollama" in settings: backend.ollama_url = settings["ollama"]
        if "model" in settings: backend.model = settings["model"]
        if "coord_units" in settings: backend.settings["coord_units"] = settings["coord_units"]
        if "profiles_dir" in settings: backend.profiles_dir = settings["profiles_dir"]
        if "nina_root" in settings: backend.nina_root = settings["nina_root"]
        if "sequence_dir" in settings: backend.sequence_dir = settings["sequence_dir"]
        if "session_metadata_dir" in settings: backend.session_metadata_dir = settings["session_metadata_dir"]
        if "guider_unit" in settings: backend.guider_unit = settings["guider_unit"]
        if "guider_pixel_scale" in settings:
            try:
                backend.settings["guider_pixel_scale"] = float(settings["guider_pixel_scale"])
            except (ValueError, TypeError):
                pass
        if "chat_context_length" in settings:
            try:
                new_len = int(settings["chat_context_length"])
                if 1 <= new_len <= 100:
                    backend.settings["chat_context_length"] = new_len
                    backend.max_chat_history = new_len
            except (ValueError, TypeError):
                pass
        for key in ["modules", "log_level", "prometheus", "session_metadata"]:
            if key in settings:
                backend.settings[key] = settings[key]
        backend.save_settings()
        return {"success": True, "message": "Настройки сохранены"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/command")
async def execute_command(request: CommandRequest):
    """Выполнение команды"""
    try:
        command = {"action": request.action, "params": request.params}
        backend.log(f"UI команда: {request.action}", "INFO")
        async def run_command():
            result = await asyncio.to_thread(backend._execute_command, command)
            backend.add_to_chat("Система", f"{request.action} → {result}")
        asyncio.create_task(run_command())
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def send_chat_message(request: ChatMessage):
    """Отправка сообщения в чат"""
    try:
        backend.add_to_chat("Вы", request.message)
        async def process():
            await asyncio.to_thread(backend.process_message, request.message)
        asyncio.create_task(process())
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ai_mode")
async def set_ai_mode(request: dict):
    """Установка режима AI"""
    backend.set_ai_mode(request.get("mode", "auto"))
    return {"success": True}


@app.get("/api/sequence")
async def get_sequence():
    """Получение статуса последовательности"""
    return sanitize_for_json(await asyncio.to_thread(backend.get_sequence_dashboard))


@app.get("/api/sequence/tree")
async def get_sequence_tree():
    """Получение дерева последовательности"""
    tree = await asyncio.to_thread(backend.build_sequence_tree)
    return sanitize_for_json(tree)


@app.get("/api/profile")
async def get_profile():
    """Получение профиля NINA"""
    return sanitize_for_json({"profile": backend.nina_profile, "path": backend.profile_path})


@app.post("/api/reload_profile")
async def reload_profile():
    """Перезагрузка профиля"""
    await asyncio.to_thread(backend.load_nina_profile)
    return {"success": True}


@app.get("/api/telemetry")
async def get_telemetry():
    """Получение детальной телеметрии"""
    return sanitize_for_json(backend.detailed_telemetry)


@app.get("/api/environment")
async def get_environment():
    """Получение данных окружающей среды"""
    return sanitize_for_json(backend.environment_data)


@app.get("/api/images")
async def get_images():
    """Получение статистики изображений"""
    return sanitize_for_json({
        "current": backend.image_stats,
        "session": backend.session_stats,
        "history": backend.image_history[-50:]
    })


@app.get("/api/guider")
async def get_guider():
    """Получение информации о гиде"""
    return sanitize_for_json(backend.guider_details)


@app.post("/api/guider/set_unit")
async def set_guider_unit(request: dict):
    """Установка единиц измерения гида"""
    unit = request.get("unit", "arcsec")
    if unit in ["pixels", "arcsec"]:
        backend.guider_unit = unit
        backend.settings["guider_unit"] = unit
        backend.save_settings()
        return {"success": True, "unit": unit}
    raise HTTPException(status_code=400, detail="Недопустимая единица")


# =====================================================================
# PROMETHEUS ENDPOINTS (из v9)
# =====================================================================
@app.get("/api/metrics")
async def get_metrics_prometheus():
    """Эндпоинт для Prometheus в text exposition format"""
    return PlainTextResponse(
        backend.prometheus.export_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )


@app.get("/api/metrics/snapshot")
async def get_metrics_snapshot():
    """JSON snapshot всех метрик для UI"""
    return sanitize_for_json({
        "snapshot": backend.prometheus.snapshot(),
        "timestamp": datetime.now().isoformat()
    })


@app.get("/api/metrics/history")
async def get_metrics_history(minutes: int = 60):
    """История метрик для построения графиков"""
    return sanitize_for_json({
        "history": backend.prometheus.get_history(minutes),
        "minutes": minutes,
        "count": len(backend.prometheus.get_history(minutes))
    })


# =====================================================================
# SESSION METADATA ENDPOINTS (из v9)
# =====================================================================
@app.get("/api/session_metadata")
async def get_session_metadata():
    """Полная сводка по сессии"""
    await asyncio.to_thread(backend.session_metadata.parse_all, True)
    return sanitize_for_json(backend.session_metadata.get_session_summary())


@app.post("/api/session_metadata/rescan")
async def rescan_session_metadata():
    """Принудительное пересканирование"""
    await asyncio.to_thread(backend.session_metadata.parse_all, True)
    return {
        "success": True,
        "summary": sanitize_for_json(backend.session_metadata.get_session_summary())
    }


# =====================================================================
# ДИАГНОСТИКА И УПРАВЛЕНИЕ
# =====================================================================
@app.post("/api/test_commands")
async def test_commands():
    """Тест всех команд API"""
    results = await asyncio.to_thread(backend.test_all_commands)
    return sanitize_for_json({"success": True, "results": results})


@app.post("/api/clear_chat")
async def clear_chat():
    """Очистка чата"""
    backend.clear_chat()
    return {"success": True}


@app.post("/api/clear_log")
async def clear_log():
    """Очистка логов"""
    backend.clear_log()
    return {"success": True}


# =====================================================================
# WEBSOCKET
# =====================================================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint для real-time обновлений"""
    await manager.connect(websocket)
    try:
        await websocket.send_json(sanitize_for_json({"type": "init", "data": backend.get_current_state()}))
        last_activity = time.time()
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                last_activity = time.time()
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_json({"type": "pong", "time": time.time()})
                except Exception:
                    pass
            except asyncio.TimeoutError:
                if time.time() - last_activity > 25:
                    try:
                        await websocket.send_json({"type": "heartbeat", "time": time.time()})
                        last_activity = time.time()
                    except Exception:
                        break
            except Exception:
                break
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)