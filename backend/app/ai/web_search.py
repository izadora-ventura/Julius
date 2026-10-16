"""Busca na web opcional para o agente de IA.

Suporta provedores gratuitos: Tavily, Serper, Brave Search ou DuckDuckGo HTML.
Desligada por padrão (WEB_SEARCH_ENABLED=false). Os provedores são tentados na
ordem de WEB_SEARCH_PROVIDER_ORDER; os que não têm chave são pulados. A consulta
vai para um serviço externo — por isso a ferramenta pede ao agente que nunca
inclua dados pessoais ou valores do usuário.
"""

import logging
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from app.config import get_settings

log = logging.getLogger("julius.ai.web_search")

MAX_RESULTS = 8
MAX_CHARS = 8000
MAX_QUERY = 300
TIMEOUT = 20.0


def _truncate(text: str, max_chars: int = MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[...truncado...]\n"


class WebSearchError(Exception):
    pass


def _search_tavily(query: str) -> dict[str, Any]:
    s = get_settings()
    api_key = s.tavily_api_key
    if not api_key:
        raise WebSearchError("Tavily não configurado")
    try:
        r = httpx.post(
            "https://api.tavily.com/search",
            json={
                "query": query,
                "search_depth": "basic",
                "max_results": MAX_RESULTS,
                "include_answer": False,
                "include_raw_content": False,
            },
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Tavily search failed: %s", type(exc).__name__)
        raise WebSearchError("Falha na busca (Tavily)") from exc
    results = []
    for res in data.get("results", [])[:MAX_RESULTS]:
        results.append(
            {
                "title": res.get("title", ""),
                "url": res.get("url", ""),
                "snippet": res.get("content", "") or res.get("snippet", ""),
            }
        )
    return {"provider": "tavily", "results": results}


def _search_serper(query: str) -> dict[str, Any]:
    s = get_settings()
    api_key = s.serper_api_key
    if not api_key:
        raise WebSearchError("Serper não configurado")
    try:
        r = httpx.post(
            "https://google.serper.dev/search",
            json={"q": query, "num": MAX_RESULTS},
            headers={"X-API-KEY": api_key},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Serper search failed: %s", type(exc).__name__)
        raise WebSearchError("Falha na busca (Serper)") from exc
    results = []
    for res in data.get("organic", [])[:MAX_RESULTS]:
        results.append(
            {
                "title": res.get("title", ""),
                "url": res.get("link", ""),
                "snippet": res.get("snippet", "") or res.get("summary", ""),
            }
        )
    return {"provider": "serper", "results": results}


def _search_brave(query: str) -> dict[str, Any]:
    s = get_settings()
    api_key = s.brave_api_key
    if not api_key:
        raise WebSearchError("Brave não configurado")
    try:
        r = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": MAX_RESULTS, "search_lang": "pt-br", "country": "BR"},
            headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Brave search failed: %s", type(exc).__name__)
        raise WebSearchError("Falha na busca (Brave)") from exc
    results = []
    web = data.get("web", {})
    for res in web.get("results", [])[:MAX_RESULTS]:
        results.append(
            {
                "title": res.get("title", ""),
                "url": res.get("url", ""),
                "snippet": res.get("description", "") or res.get("snippet", ""),
            }
        )
    return {"provider": "brave", "results": results}


def _ddg_target(href: str) -> str:
    """Links do DuckDuckGo HTML vêm como //duckduckgo.com/l/?uddg=<url real>."""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return target if target.startswith(("http://", "https://")) else ""
    return href if parsed.scheme in ("http", "https") else ""


class _DDGParser(HTMLParser):
    """Extrai título, link e resumo da página HTML do DuckDuckGo (sem dependências)."""

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._field: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if "result__a" in classes:
            self.results.append({"title": "", "url": _ddg_target(a.get("href") or ""), "snippet": ""})
            self._field = "title"
        elif "result__snippet" in classes and self.results:
            self._field = "snippet"

    def handle_endtag(self, tag: str) -> None:
        if tag in ("a", "td", "div") and self._field:
            self._field = None

    def handle_data(self, data: str) -> None:
        if self._field and self.results:
            self.results[-1][self._field] += data


def _search_duckduckgo(query: str) -> dict[str, Any]:
    try:
        r = httpx.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query, "kl": "br-pt"},
            headers={"User-Agent": "Mozilla/5.0 (compatible; JULIUS)"},
            timeout=TIMEOUT,
            follow_redirects=True,
        )
        r.raise_for_status()
        html = r.text
    except httpx.HTTPError as exc:
        log.warning("DuckDuckGo search failed: %s", type(exc).__name__)
        raise WebSearchError("Falha na busca (DuckDuckGo)") from exc
    parser = _DDGParser()
    parser.feed(html)
    results = [
        {"title": " ".join(x["title"].split()), "url": x["url"], "snippet": " ".join(x["snippet"].split())}
        for x in parser.results
        if x["url"]
    ][:MAX_RESULTS]
    return {"provider": "duckduckgo", "results": results}


PROVIDERS = {
    "tavily": _search_tavily,
    "serper": _search_serper,
    "brave": _search_brave,
    "duckduckgo": _search_duckduckgo,
}


def search_web(query: str) -> dict[str, Any]:
    q = (query or "").strip()[:MAX_QUERY]
    if not q:
        raise WebSearchError("Consulta vazia")
    s = get_settings()
    if not s.web_search_enabled:
        raise WebSearchError("Busca na web desativada (WEB_SEARCH_ENABLED=false)")
    order = [p.strip().lower() for p in s.web_search_provider_order.split(",") if p.strip()]
    errors: list[str] = []
    for provider in order:
        fn = PROVIDERS.get(provider)
        if fn is None:
            errors.append(f"Provedor desconhecido: {provider}")
            continue
        try:
            res = fn(q)
        except WebSearchError as exc:
            errors.append(str(exc))
            continue
        res["query"] = q
        res["summary"] = _truncate(
            "\n\n".join(f"- {r['title']}: {r['snippet']} ({r['url']})" for r in res["results"])
        )
        return res
    raise WebSearchError("; ".join(errors) if errors else "Nenhum provedor de busca configurado")
