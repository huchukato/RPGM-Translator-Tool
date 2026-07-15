#!/usr/bin/env python3
"""
RPGM-Translator - Translator Module
Backend di traduzione: Google, Bing, OpenRouter, llama_cpp.
Adattato dal modulo tr_translator.py di Ren'Py Translator.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal
import json
import random
import re
import threading
import time
import requests

try:
    from deep_translator import GoogleTranslator
    GOOGLE_OK = True
except ImportError:
    GOOGLE_OK = False

try:
    from llama_cpp import Llama
    LLAMA_OK = True
except ImportError:
    LLAMA_OK = False

try:
    from huggingface_hub import hf_hub_download
    HF_OK = True
except ImportError:
    HF_OK = False


OPENROUTER_FREE_MODELS = [
    "google/gemma-2-9b-it:free",
    "google/gemma-2-27b-it:free",
    "meta-llama/llama-3-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "mistralai/mistral-nemo:free",
    "qwen/qwen-2-7b-instruct:free",
    "deepseek/deepseek-chat-v3.1:free",
]

LANG_NAMES = {
    "en": "English", "it": "Italian", "fr": "French", "es": "Spanish",
    "de": "German", "pt": "Portuguese", "ja": "Japanese", "zh": "Chinese",
    "ar": "Arabic", "ru": "Russian", "ko": "Korean",
}


@dataclass
class TranslatorConfig:
    backend: Literal["google", "google_turbo", "bing", "bing_turbo", "bing_ultra", "openrouter", "llama"] = "bing_ultra"
    source_lang: str = "en"
    target_lang: str = "it"
    libre_endpoint: str = "http://localhost:5000"
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemma-2-9b-it:free"
    llama_model_repo: str = "llmfan46/gemma-4-E4B-it-ultra-uncensored-heretic-GGUF"
    llama_model_file: str = ""
    preserve_names: bool = False
    translate_menu: bool = False
    character_names: frozenset = frozenset()
    timeout_s: int = 30
    batch_size: int = 50
    translation_profile: Literal["Safe", "Balanced", "Fast"] = "Balanced"


class TranslationError(RuntimeError):
    pass


class Translator:
    RE_TOKEN = re.compile(
        r"(\\\\n|\\\\\"|<[^>]*>|\{[^}]*\}|\[[^\]]*\]|"
        r"\\[A-Za-z]+(?:\[\d+\])?|\\[{}!.|^$><\\]|"
        r"%\([^)]+\)[#0\- +]?\d*(?:\.\d+)?[a-zA-Z]|%[sdrof]|%%|https?://[^\s]+)"
    )

    def __init__(self, cfg: TranslatorConfig):
        self.cfg = cfg
        self.cache: dict[str, str] = {}
        self.cancelled = False
        self._load_disk_cache()
        self._mirror_health: dict[str, dict] = {
            ep: {"fails": 0, "banned_until": 0.0} for ep in self._GOOGLE_MIRRORS
        }
        self._gt_global_cooldown: float = 0.0
        self._gt_consecutive_429: int = 0
        self._gt_adaptive_delay: float = 0.0
        self._gt_lock = threading.Lock()

    def _cache_path(self) -> Path:
        lang_pair = f"{self.cfg.source_lang}_{self.cfg.target_lang}"
        return Path.home() / ".cache" / "rpgm-translator" / f"translation_cache_{lang_pair}.json"

    def _load_disk_cache(self):
        try:
            cache_path = self._cache_path()
            if cache_path.exists():
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.cache = {str(key): str(value) for key, value in data.items()}
        except Exception:
            self.cache = {}

    def _save_disk_cache(self):
        try:
            cache_path = self._cache_path()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def cancel(self):
        self.cancelled = True

    def translate_many(
        self,
        texts: list[str],
        progress_cb: Callable[[int, int], None] | None = None,
        log_cb: Callable[[str, str], None] | None = None,
    ) -> dict[str, str]:
        unique = list(dict.fromkeys(t for t in texts if t))
        total = len(unique)

        if self.cfg.preserve_names:
            preserved = {t for t in unique if self._is_name(t)}
            for name in preserved:
                self.cache[name] = name

        pending = [text for text in unique if text not in self.cache]
        cached_count = total - len(pending)
        if progress_cb and cached_count:
            progress_cb(cached_count, total)

        if pending and self.cfg.backend in ("bing", "bing_turbo", "bing_ultra", "google", "google_turbo"):
            if self.cancelled:
                raise TranslationError("Traduzione annullata.")
            translated = self._translate_batch(pending, log_cb, progress_cb, cached_count, total)
            for orig, tr in zip(pending, translated):
                self.cache[orig] = tr
        else:
            done = cached_count
            batches = [pending[i:i + self.cfg.batch_size] for i in range(0, len(pending), self.cfg.batch_size)]
            for batch in batches:
                if self.cancelled:
                    raise TranslationError("Traduzione annullata.")
                translated = self._translate_batch(batch, log_cb)
                for orig, tr in zip(batch, translated):
                    self.cache[orig] = tr
                    done += 1
                    if progress_cb:
                        progress_cb(done, total)

        self._save_disk_cache()
        return {text: self.cache.get(text, "") for text in unique}

    def _translate_batch(self, texts: list[str], log_cb=None, progress_cb=None, done_offset=0, total=0) -> list[str]:
        protected, maps = zip(*[self._protect(t) for t in texts]) if texts else ([], [])
        protected = list(protected); maps = list(maps)
        raw = self._raw_batch(protected, log_cb, progress_cb, done_offset, total)
        return [self._restore(r, m) for r, m in zip(raw, maps)]

    def _raw_batch(self, texts: list[str], log_cb=None, progress_cb=None, done_offset=0, total=0) -> list[str]:
        b = self.cfg.backend
        if b == "google":
            return self._google(texts, progress_cb, done_offset, total)
        elif b == "google_turbo":
            return self._google_turbo(texts, progress_cb, done_offset, total)
        elif b == "bing":
            return self._bing(texts, progress_cb, done_offset, total)
        elif b == "bing_turbo":
            return self._bing_turbo(texts, progress_cb, done_offset, total)
        elif b == "bing_ultra":
            return self._bing_ultra(texts, progress_cb, done_offset, total)
        elif b == "openrouter":
            return self._openrouter(texts)
        elif b == "llama":
            return self._llama(texts, log_cb)
        raise TranslationError(f"Backend sconosciuto: {b}")

    _GOOGLE_CHAR_LIMIT = 5000
    _GOOGLE_TURBO_CHAR_LIMIT = 950
    _GOOGLE_TURBO_WORKERS = 6
    _GOOGLE_TURBO_SEP = "\n<<<SEP>>>\n"
    _GOOGLE_MIRRORS = [
        "https://translate.google.com/m",
        "https://translate.google.de/m",
        "https://translate.google.fr/m",
        "https://translate.google.es/m",
        "https://translate.google.it/m",
        "https://translate.google.co.uk/m",
        "https://translate.google.com.tr/m",
        "https://translate.google.ru/m",
        "https://translate.google.co.jp/m",
        "https://translate.google.ca/m",
        "https://translate.google.com.au/m",
        "https://translate.google.pl/m",
    ]
    _MIRROR_BAN_TIME = 120
    _MIRROR_MAX_FAILS = 5
    _TURBO_PROFILES = {
        "Safe": (2, 0.35),
        "Balanced": (4, 0.12),
        "Fast": (6, 0.0),
    }

    def _turbo_profile(self) -> tuple[int, float]:
        return self._TURBO_PROFILES.get(self.cfg.translation_profile, self._TURBO_PROFILES["Balanced"])

    def _google(self, texts: list[str], progress_cb=None, done_offset=0, total=0) -> list[str]:
        if not GOOGLE_OK:
            raise TranslationError("deep-translator non installato: pip install deep-translator")
        tr = GoogleTranslator(source=self.cfg.source_lang, target=self.cfg.target_lang,
                              timeout=self.cfg.timeout_s)
        chunks: list[tuple[list[int], list[str]]] = []
        cur_idx: list[int] = []; cur_texts: list[str] = []; cur_len = 0
        for i, text in enumerate(texts):
            t = text[:self._GOOGLE_CHAR_LIMIT]
            if cur_texts and cur_len + len(t) > self._GOOGLE_CHAR_LIMIT:
                chunks.append((cur_idx, cur_texts))
                cur_idx = []; cur_texts = []; cur_len = 0
            cur_idx.append(i); cur_texts.append(t); cur_len += len(t)
        if cur_texts:
            chunks.append((cur_idx, cur_texts))

        results = list(texts)
        done = done_offset
        for indices, chunk_texts in chunks:
            try:
                res = tr.translate_batch(chunk_texts)
                for i, r in zip(indices, res):
                    results[i] = r if r else texts[i]
            except Exception:
                for i, t in zip(indices, chunk_texts):
                    try:
                        results[i] = tr.translate(t) or texts[i]
                    except Exception:
                        pass
            done += len(indices)
            if progress_cb and total:
                progress_cb(min(done, total), total)
        return results

    _GT_UA_LIST = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    ]

    def _gt_next_mirror(self) -> str:
        now = time.time()
        if now < self._gt_global_cooldown:
            time.sleep(min(self._gt_global_cooldown - now, 5.0))
        available = [ep for ep, h in self._mirror_health.items() if time.time() >= h["banned_until"]]
        if not available:
            earliest = min(h["banned_until"] for h in self._mirror_health.values())
            wait = min(earliest - time.time(), 10.0)
            if wait > 0:
                time.sleep(wait)
            for h in self._mirror_health.values():
                h["fails"] = 0; h["banned_until"] = 0.0
            available = list(self._mirror_health.keys())
        return available[0]

    def _gt_mark_ok(self, mirror: str):
        with self._gt_lock:
            self._gt_consecutive_429 = max(0, self._gt_consecutive_429 - 1)
            self._gt_adaptive_delay = max(0.0, self._gt_adaptive_delay - 0.005)
            if mirror in self._mirror_health:
                self._mirror_health[mirror]["fails"] = 0

    def _gt_mark_fail(self, mirror: str, is_429: bool = False):
        with self._gt_lock:
            if is_429:
                self._gt_consecutive_429 += 1
                self._gt_adaptive_delay = min(2.0, self._gt_adaptive_delay + 0.15)
                wait = min(3.0 * (2 ** (self._gt_consecutive_429 - 1)), 30.0)
                self._gt_global_cooldown = time.time() + wait
            if mirror in self._mirror_health:
                h = self._mirror_health[mirror]
                h["fails"] += 1
                if h["fails"] >= self._MIRROR_MAX_FAILS:
                    h["banned_until"] = time.time() + self._MIRROR_BAN_TIME

    def _gt_make_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({"Accept-Language": "en-US,en;q=0.9"})
        return session

    def _gt_translate_chunk(self, chunk_text: str, src: str, tgt: str, session: requests.Session | None = None) -> list[str]:
        from urllib.parse import quote
        sep = self._GOOGLE_TURBO_SEP
        mirror = self._gt_next_mirror()
        for attempt in range(3):
            try:
                _, request_delay = self._turbo_profile()
                with self._gt_lock:
                    adaptive_delay = self._gt_adaptive_delay
                delay = request_delay * random.uniform(0.75, 1.25) + adaptive_delay
                if delay:
                    time.sleep(delay)
                ua = self._GT_UA_LIST[attempt % len(self._GT_UA_LIST)]
                url = f"{mirror}?sl={src}&tl={tgt}&q={quote(chunk_text)}"
                client = session or requests
                r = client.get(url, headers={"User-Agent": ua}, timeout=self.cfg.timeout_s)
                is_429 = r.status_code == 429
                r.raise_for_status()
                m = re.search(r'class="(?:result-container|t0|gt-cd)"[^>]*>(.*?)</div>', r.text, re.DOTALL)
                if not m:
                    m = re.search(r'class="result-container">(.*?)</div>', r.text, re.DOTALL)
                if not m:
                    self._gt_mark_fail(mirror)
                    mirror = self._gt_next_mirror()
                    continue
                translated = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                if not translated:
                    self._gt_mark_fail(mirror)
                    mirror = self._gt_next_mirror()
                    continue
                self._gt_mark_ok(mirror)
                import html as _html
                translated = _html.unescape(translated)
                parts = translated.split(sep)
                originals = chunk_text.split(sep)
                if len(parts) == len(originals):
                    return parts
                return []
            except requests.exceptions.HTTPError as e:
                is_429 = e.response is not None and e.response.status_code == 429
                self._gt_mark_fail(mirror, is_429=is_429)
                mirror = self._gt_next_mirror()
                time.sleep((1.5 ** attempt) * 0.5)
            except Exception:
                self._gt_mark_fail(mirror)
                mirror = self._gt_next_mirror()
                time.sleep((1.5 ** attempt) * 0.3)
        return [""] * len(chunk_text.split(sep))

    def _google_turbo(self, texts: list[str], progress_cb=None, done_offset=0, total=0) -> list[str]:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        src, tgt = self.cfg.source_lang, self.cfg.target_lang
        sep = self._GOOGLE_TURBO_SEP
        lim = self._GOOGLE_TURBO_CHAR_LIMIT
        workers, _ = self._turbo_profile()
        thread_local = threading.local()

        chunks: list[tuple[list[int], str]] = []
        cur_idx: list[int] = []; cur_parts: list[str] = []; cur_len = 0
        for i, text in enumerate(texts):
            t = text.replace("<<<SEP>>>", "[SEP]")
            needed = len(t) + (len(sep) if cur_parts else 0)
            if cur_parts and cur_len + needed > lim:
                chunks.append((cur_idx, sep.join(cur_parts)))
                cur_idx = []; cur_parts = []; cur_len = 0
            cur_idx.append(i); cur_parts.append(t); cur_len += needed
        if cur_parts:
            chunks.append((cur_idx, sep.join(cur_parts)))

        results = list(texts)
        done_count = [done_offset]

        def do_chunk(chunk_idx_data):
            _, (indices, chunk_text) = chunk_idx_data
            session = getattr(thread_local, "session", None)
            if session is None:
                session = self._gt_make_session()
                thread_local.session = session
            parts = self._gt_translate_chunk(chunk_text, src, tgt, session)
            if len(parts) != len(indices):
                originals = chunk_text.split(sep)
                parts = []
                for orig in originals:
                    fb = self._gt_translate_chunk(orig, src, tgt, session)
                    parts.append(fb[0] if fb else orig)
            return indices, parts

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(do_chunk, item): item for item in enumerate(chunks)}
            for fut in as_completed(futures):
                if self.cancelled:
                    ex.shutdown(wait=False, cancel_futures=True)
                    raise TranslationError("Traduzione annullata.")
                try:
                    indices, parts = fut.result()
                    for i, p in zip(indices, parts):
                        if p:
                            results[i] = p
                    with self._gt_lock:
                        done_count[0] += len(indices)
                        if progress_cb and total:
                            progress_cb(min(done_count[0], total), total)
                except Exception:
                    pass
        return results

    _BING_USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    ]
    _BING_ACCEPT_LANGS = [
        "en-US,en;q=0.9", "en-US,en;q=0.9,es;q=0.8",
        "en-GB,en;q=0.9", "en-CA,en-US;q=0.7,en;q=0.3",
    ]
    _BING_CHAR_LIMIT = 900
    _BING_SEP = "\n<<<SEP>>>\n"

    def _bing_make_session(self, base_url: str = "https://www.bing.com", idx: int = 0) -> tuple:
        import random
        session = requests.Session()
        session.headers.update({
            "User-Agent": self._BING_USER_AGENTS[idx % len(self._BING_USER_AGENTS)],
            "Accept-Language": self._BING_ACCEPT_LANGS[idx % len(self._BING_ACCEPT_LANGS)],
        })
        ig_val = ""; key_val = ""; token_val = ""
        try:
            home = session.get(f"{base_url}/translator", timeout=10)
            html = home.text
            m_ig = re.search(r'IG:"([0-9A-F]+)"', html)
            m_abuse = re.search(
                r'var params_AbusePreventionHelper\s*=\s*\[(\d+),"([^"]+)",(\d+)\]', html
            )
            if m_ig:
                ig_val = m_ig.group(1)
            if m_abuse:
                key_val = m_abuse.group(1)
                token_val = m_abuse.group(2)
        except Exception:
            pass
        return session, ig_val, key_val, token_val

    def _bing_split_chunks(self, texts: list[str]) -> list[tuple[list[int], str]]:
        chunks = []
        cur_indices = []
        cur_parts = []
        cur_len = 0
        for i, text in enumerate(texts):
            t = text.replace("<<<SEP>>>", "[SEP]")
            needed = len(t) + (len(self._BING_SEP) if cur_parts else 0)
            if cur_parts and cur_len + needed > self._BING_CHAR_LIMIT:
                chunks.append((cur_indices, self._BING_SEP.join(cur_parts)))
                cur_indices = []; cur_parts = []; cur_len = 0
            cur_indices.append(i)
            cur_parts.append(t)
            cur_len += needed
        if cur_parts:
            chunks.append((cur_indices, self._BING_SEP.join(cur_parts)))
        return chunks

    def _bing_post(self, session, text: str, src: str, tgt: str,
                   ig: str, key: str, token: str,
                   base_url: str = "https://www.bing.com") -> str:
        r = session.post(
            f"{base_url}/ttranslatev3",
            params={"isVertical": "1", "IG": ig, "IID": "translator.5024"},
            data={"fromLang": src, "to": tgt, "text": text, "token": token, "key": key},
            timeout=self.cfg.timeout_s,
        )
        return r.json()[0]["translations"][0]["text"]

    def _bing_translate_chunk(self, session, chunk_text: str, src: str, tgt: str,
                              ig: str, key: str, token: str,
                              base_url: str = "https://www.bing.com") -> list[str]:
        n_expected = chunk_text.count(self._BING_SEP) + 1
        raw = self._bing_post(session, chunk_text, src, tgt, ig, key, token, base_url)
        parts = raw.split(self._BING_SEP)
        if len(parts) == n_expected:
            return parts
        originals = chunk_text.split(self._BING_SEP)
        results = []
        for orig in originals:
            try:
                results.append(self._bing_post(session, orig, src, tgt, ig, key, token, base_url))
            except Exception:
                results.append(orig)
        return results

    def _bing(self, texts: list[str], progress_cb=None, done_offset=0, total=0) -> list[str]:
        src, tgt = self.cfg.source_lang, self.cfg.target_lang
        session, ig, key, token = self._bing_make_session()
        results = list(texts)
        done = done_offset
        for indices, chunk_text in self._bing_split_chunks(texts):
            try:
                parts = self._bing_translate_chunk(session, chunk_text, src, tgt, ig, key, token)
                for i, p in zip(indices, parts):
                    results[i] = p.strip()
            except Exception:
                pass
            done += len(indices)
            if progress_cb and total:
                progress_cb(min(done, total), total)
        return results

    def _bing_turbo(self, texts: list[str], progress_cb=None, done_offset=0, total=0) -> list[str]:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        src, tgt = self.cfg.source_lang, self.cfg.target_lang
        n = 3
        sessions = [self._bing_make_session(idx=i) for i in range(n)]
        chunks = self._bing_split_chunks(texts)
        results = list(texts)
        done_count = [done_offset]
        lock = threading.Lock()

        def do_chunk(chunk_idx_data):
            chunk_idx, (indices, chunk_text) = chunk_idx_data
            sess, ig, key, token = sessions[chunk_idx % n]
            try:
                parts = self._bing_translate_chunk(sess, chunk_text, src, tgt, ig, key, token)
                return indices, parts
            except Exception:
                return indices, None

        with ThreadPoolExecutor(max_workers=n) as ex:
            futures = [ex.submit(do_chunk, (i, c)) for i, c in enumerate(chunks)]
            for f in as_completed(futures):
                indices, parts = f.result()
                if parts:
                    for i, p in zip(indices, parts):
                        results[i] = p.strip()
                with lock:
                    done_count[0] += len(indices)
                    if progress_cb and total:
                        progress_cb(min(done_count[0], total), total)
        return results

    def _bing_ultra(self, texts: list[str], progress_cb=None, done_offset=0, total=0) -> list[str]:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        src, tgt = self.cfg.source_lang, self.cfg.target_lang
        workers, _ = self._turbo_profile()
        bases = (["https://www.bing.com", "https://cn.bing.com"] * workers)[:workers]
        sessions = [self._bing_make_session(base_url=b, idx=i) for i, b in enumerate(bases)]
        chunks = self._bing_split_chunks(texts)
        results = list(texts)
        done_count = [done_offset]
        lock = threading.Lock()

        def do_chunk(chunk_idx_data):
            chunk_idx, (indices, chunk_text) = chunk_idx_data
            sess, ig, key, token = sessions[chunk_idx % len(sessions)]
            base = bases[chunk_idx % len(bases)]
            try:
                parts = self._bing_translate_chunk(sess, chunk_text, src, tgt, ig, key, token, base)
                return indices, parts
            except Exception:
                try:
                    s, g, k, tk = sessions[0]
                    parts = self._bing_translate_chunk(s, chunk_text, src, tgt, g, k, tk)
                    return indices, parts
                except Exception:
                    return indices, None

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(do_chunk, (i, c)) for i, c in enumerate(chunks)]
            for f in as_completed(futures):
                indices, parts = f.result()
                if parts:
                    for i, p in zip(indices, parts):
                        results[i] = p.strip()
                with lock:
                    done_count[0] += len(indices)
                    if progress_cb and total:
                        progress_cb(min(done_count[0], total), total)
        return results

    def _openrouter(self, texts: list[str]) -> list[str]:
        src = LANG_NAMES.get(self.cfg.source_lang, self.cfg.source_lang)
        tgt = LANG_NAMES.get(self.cfg.target_lang, self.cfg.target_lang)
        headers = {"Content-Type": "application/json"}
        if self.cfg.openrouter_api_key:
            headers["Authorization"] = f"Bearer {self.cfg.openrouter_api_key}"
        results = []
        for text in texts:
            try:
                r = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": self.cfg.openrouter_model,
                        "messages": [
                            {"role": "system", "content": f"Translate from {src} to {tgt}. Only return the translation."},
                            {"role": "user", "content": text}
                        ],
                        "max_tokens": 1000,
                        "temperature": 0.3,
                    },
                    timeout=self.cfg.timeout_s
                )
                r.raise_for_status()
                results.append(r.json()["choices"][0]["message"]["content"].strip())
            except Exception:
                results.append(text)
        return results

    def _llama(self, texts: list[str], log_cb=None) -> list[str]:
        if not LLAMA_OK:
            raise TranslationError("llama-cpp-python non installato")
        if not HF_OK:
            raise TranslationError("huggingface-hub non installato")
        model_path = self._get_llama_model(log_cb)
        llm = Llama(model_path=model_path, n_ctx=2048, n_threads=4, verbose=False)
        src = LANG_NAMES.get(self.cfg.source_lang, self.cfg.source_lang)
        tgt = LANG_NAMES.get(self.cfg.target_lang, self.cfg.target_lang)
        results = []
        for text in texts:
            try:
                prompt = f"<start_of_turn>user\nTranslate from {src} to {tgt}: {text}<end_of_turn>\n<start_of_turn>model\n"
                resp = llm(prompt, max_tokens=512, temperature=0.1, stop=["<end_of_turn>"], echo=False)
                translated = resp["choices"][0]["text"].strip() if resp and resp.get("choices") else text
                results.append(translated or text)
            except Exception:
                results.append(text)
        return results

    def _get_llama_model(self, log_cb=None) -> str:
        cache = Path.home() / ".cache" / "rpgm-translator" / "models"
        cache.mkdir(parents=True, exist_ok=True)
        model_file = cache / self.cfg.llama_model_file
        if model_file.exists():
            return str(model_file)
        if log_cb:
            log_cb("system", f"Download modello {self.cfg.llama_model_file}...")
        path = hf_hub_download(repo_id=self.cfg.llama_model_repo,
                               filename=self.cfg.llama_model_file,
                               local_dir=str(cache))
        return path

    def _protect(self, text: str):
        mapping = {}
        counter = 0
        def rep(m):
            nonlocal counter
            k = f"\u27eaRNT{counter}\u27eb"; mapping[k] = m.group(0); counter += 1; return k
        return self.RE_TOKEN.sub(rep, text), mapping

    def _restore(self, text: str, mapping: dict) -> str:
        for k, v in mapping.items():
            text = text.replace(k, v)
        def norm(s): return re.sub(r"[^A-Za-z0-9]", "", s).upper()
        norm_map = {norm(k): v for k, v in mapping.items()}
        if norm_map:
            def repl(m):
                return norm_map.get(norm(m.group(0)), m.group(0))
            text = re.sub(r"(?:\u27ea\s*)?R\s*N\s*T\s*\d+(?:\s*\u27eb)?", repl, text, flags=re.IGNORECASE)
        return text

    def _is_name(self, text: str) -> bool:
        if not self.cfg.character_names:
            return False
        return text in self.cfg.character_names
