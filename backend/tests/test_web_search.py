"""Busca na web do agente: desligada por padrão, ordem de provedores e leitura do DuckDuckGo."""

import httpx
import pytest

from app.ai import web_search
from app.ai.providers import AIUnavailable, ChatReply, set_provider_for_tests
from app.config import get_settings

DDG_HTML = """
<div class="result results_links">
  <h2 class="result__title">
    <a rel="nofollow" class="result__a"
       href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.bcb.gov.br%2Fcontrolenflacao%2Ftaxaselic&amp;rut=abc">
       Taxa <b>Selic</b> - Banco Central</a>
  </h2>
  <a class="result__snippet" href="//duckduckgo.com/l/?uddg=x">A taxa <b>Selic</b> é a taxa básica de juros.</a>
</div>
<div class="result"><a class="result__a" href="/y.js?ad=1">Anúncio</a></div>
<div class="result"><a class="result__a" href="javascript:alert(1)">Ruim</a></div>
"""


class Recorder:
    """Provedor falso: pede uma busca e depois responde; guarda o que recebeu."""

    name = "fake"

    def __init__(self, script):
        self.script, self.seen, self.tools = list(script), [], []

    def generate_json(self, *a, **kw):
        raise AIUnavailable("não usado")

    def chat(self, messages, tools):
        self.seen.append(messages)
        self.tools.append([t["name"] for t in tools])
        step = self.script.pop(0)
        if isinstance(step, str):
            return ChatReply(text=step, tool_calls=[], raw_message={"role": "assistant", "content": step})
        calls = [{"id": f"c{i}", "name": n, "arguments": a} for i, (n, a) in enumerate(step)]
        raw = {"role": "assistant", "content": None, "tool_calls": []}
        return ChatReply(text=None, tool_calls=calls, raw_message=raw)


@pytest.fixture
def provider():
    holder = {}

    def install(script):
        holder["p"] = Recorder(script)
        set_provider_for_tests(holder["p"])
        return holder["p"]

    yield install
    set_provider_for_tests(None)


def fake_http(monkeypatch, routes: dict[str, httpx.Response | Exception]):
    calls = []

    def handler(method):
        def call(url, **kw):
            calls.append(url)
            res = routes[url]
            if isinstance(res, Exception):
                raise res
            res.request = httpx.Request(method, url)
            return res

        return call

    monkeypatch.setattr(web_search.httpx, "post", handler("POST"))
    monkeypatch.setattr(web_search.httpx, "get", handler("GET"))
    return calls


def enable(monkeypatch, order="tavily,serper,brave,duckduckgo", **keys):
    s = get_settings()
    monkeypatch.setattr(s, "web_search_enabled", True)
    monkeypatch.setattr(s, "web_search_provider_order", order)
    for k in ("tavily_api_key", "serper_api_key", "brave_api_key"):
        monkeypatch.setattr(s, k, keys.get(k, ""))


def ask(api, q):
    r = api.post("/api/assistant/ask", {"question": q})
    assert r.status_code == 200, r.text
    return r.json()


def test_disabled_by_default_tool_not_offered_and_refused(api, provider, monkeypatch):
    calls = fake_http(monkeypatch, {})
    fake = provider([[("web_search", {"query": "selic hoje"})], "Não consegui buscar."])
    ask(api, "qual a selic hoje?")
    assert "web_search" not in fake.tools[0]
    assert "web_search" not in fake.seen[0][0]["content"]  # regra 6 fora do prompt
    assert "desativada" in fake.seen[1][-1]["content"]  # chamada forçada é recusada
    assert calls == []  # nada saiu para a internet


def test_agent_uses_duckduckgo_when_no_keys(api, provider, monkeypatch):
    enable(monkeypatch)
    calls = fake_http(monkeypatch, {"https://html.duckduckgo.com/html/": httpx.Response(200, text=DDG_HTML)})
    fake = provider([[("web_search", {"query": "taxa selic atual"})], "A Selic é definida pelo Copom."])
    r = ask(api, "qual a taxa selic atual?")
    assert r["engine"] == "ai" and r["data"]["tools"] == ["web_search"]
    assert "web_search" in fake.tools[0] and "web_search" in fake.seen[0][0]["content"]
    assert calls == ["https://html.duckduckgo.com/html/"]  # provedores sem chave são pulados
    tool_msg = fake.seen[1][-1]["content"]
    assert "https://www.bcb.gov.br/controlenflacao/taxaselic" in tool_msg  # link real, não o redirecionador
    assert "Taxa Selic - Banco Central" in tool_msg and "taxa básica de juros" in tool_msg
    assert "Anúncio" not in tool_msg and "javascript" not in tool_msg


def test_provider_order_and_fallback(monkeypatch):
    enable(monkeypatch, order="serper,brave", serper_api_key="k1", brave_api_key="k2")
    brave = {"web": {"results": [{"title": "T", "url": "https://x.org", "description": "D"}]}}
    calls = fake_http(
        monkeypatch,
        {
            "https://google.serper.dev/search": httpx.Response(500),
            "https://api.search.brave.com/res/v1/web/search": httpx.Response(200, json=brave),
        },
    )
    res = web_search.search_web("  feriados 2026  ")
    assert res["provider"] == "brave" and res["query"] == "feriados 2026"
    assert res["results"] == [{"title": "T", "url": "https://x.org", "snippet": "D"}]
    assert calls == ["https://google.serper.dev/search", "https://api.search.brave.com/res/v1/web/search"]


def test_all_providers_fail_reports_each(monkeypatch):
    enable(monkeypatch, order="tavily,duckduckgo,bing")
    fake_http(monkeypatch, {"https://html.duckduckgo.com/html/": httpx.ConnectError("sem rede")})
    with pytest.raises(web_search.WebSearchError) as exc:
        web_search.search_web("x")
    msg = str(exc.value)
    assert "Tavily não configurado" in msg and "DuckDuckGo" in msg and "bing" in msg
    with pytest.raises(web_search.WebSearchError):
        web_search.search_web("   ")
