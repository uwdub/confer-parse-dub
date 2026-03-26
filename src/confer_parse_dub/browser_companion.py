"""Browser companion — opens a headful browser that follows along with normalization."""

import queue
import threading
import urllib.parse

from confer_parse_dub.models.paper import Affiliation

_STOP = object()  # Sentinel value that tells the browser thread to exit.


class BrowserCompanion:
    """
    Manages a persistent headful browser window in a background thread.

    Playwright's sync API runs its own event loop, which conflicts with
    questionary's use of asyncio.run().  Running Playwright in a dedicated
    daemon thread keeps the two loops isolated.

    Tabs are reused across items — each navigation updates a tab in place so
    the browser window position stays stable.

    The browser opens lazily on first use and closes when `close()` is called.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[list[str] | object] = queue.Queue()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Pipeline-facing API
    # ------------------------------------------------------------------

    def navigate_for_name(
        self,
        name: str,
        affiliations: list[Affiliation] | None = None,
        paper_title: str | None = None,
    ) -> None:
        """Open searches for the person and, if provided, for the paper."""
        parts = [name]
        for affil in affiliations or []:
            if affil.institution:
                parts.append(affil.institution)
                break
        query = " ".join(parts)
        urls = [
            "https://duckduckgo.com/?q=" + urllib.parse.quote_plus(query),
            "https://scholar.google.com/scholar?q=" + urllib.parse.quote_plus(query),
        ]
        if paper_title:
            urls.append(
                "https://scholar.google.com/scholar?q=" + urllib.parse.quote_plus(paper_title)
            )
        self._navigate_urls(urls)

    def navigate_for_split(
        self,
        value: str,
        parts: list[str],
        author_name: str | None = None,
    ) -> None:
        """Open searches to help decide whether to split a slash-separated value.

        Opens the full value (to check whether it is a recognised single entity),
        followed by one tab per part (to verify each part is its own entity), and
        optionally a tab for the person who listed this value.
        """
        ddg = "https://duckduckgo.com/?q="
        wiki = "https://en.wikipedia.org/w/index.php?search="
        urls = [
            ddg + urllib.parse.quote_plus(value),
            wiki + urllib.parse.quote_plus(value),
        ]
        for part in parts:
            urls.append(ddg + urllib.parse.quote_plus(part))
        if author_name:
            urls.append(ddg + urllib.parse.quote_plus(author_name + " " + value))
        self._navigate_urls(urls)

    def navigate_for_affiliation(
        self,
        affiliations: list[Affiliation],
        author_name: str | None = None,
        paper_title: str | None = None,
        internal: bool = False,
    ) -> None:
        """
        Open searches relevant to resolving the affiliation.

        Internal (institution is ours): focus on finding the person's unit/lab.
        External (unfamiliar institution): focus on identifying the institution.
        """
        institution = next((a.institution for a in affiliations if a.institution), None)
        if not institution:
            return

        ddg = "https://duckduckgo.com/?q="
        scholar = "https://scholar.google.com/scholar?q="
        wiki = "https://en.wikipedia.org/w/index.php?search="

        if internal:
            # We know the institution — find the person's department/lab.
            person_inst = (author_name + " " + institution) if author_name else institution
            urls = [
                ddg + urllib.parse.quote_plus(person_inst),
                scholar + urllib.parse.quote_plus(person_inst),
            ]
        else:
            # Unfamiliar institution — identify it first, then find the person.
            affil = next(a for a in affiliations if a.institution)
            inst_parts = [institution]
            if affil.city:
                inst_parts.append(affil.city)
            if affil.state:
                inst_parts.append(affil.state)
            elif affil.country:
                inst_parts.append(affil.country)
            inst_query = " ".join(inst_parts)
            urls = [
                ddg + urllib.parse.quote_plus(inst_query),
                wiki + urllib.parse.quote_plus(institution),
            ]
            if author_name:
                urls.append(ddg + urllib.parse.quote_plus(author_name + " " + institution))

        if paper_title:
            urls.append(scholar + urllib.parse.quote_plus(paper_title))

        self._navigate_urls(urls)

    def close(self) -> None:
        """Signal the browser thread to stop and wait for it to finish."""
        if self._thread is not None and self._thread.is_alive():
            self._queue.put(_STOP)
            self._thread.join(timeout=5.0)
        self._thread = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _navigate_urls(self, urls: list[str]) -> None:
        """Ensure the browser thread is running and enqueue a set of URLs."""
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        self._queue.put(urls)

    def _run(self) -> None:
        """Browser thread — owns the entire Playwright session."""
        from playwright.sync_api import BrowserContext, Page, sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=False,
                args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
                ignore_default_args=["--enable-automation"],
            )
            # One context = one window; all pages are tabs within it.
            # no_viewport=True lets the OS control the window size instead of
            # Playwright imposing its default 1280x720 fixed viewport.
            ctx: BrowserContext = browser.new_context(no_viewport=True)
            pages: list[Page] = []

            while True:
                try:
                    item = self._queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                if item is _STOP:
                    break

                urls: list[str] = list(item)  # type: ignore[arg-type]

                # Grow the tab strip if this batch needs more tabs than we have.
                while len(pages) < len(urls):
                    pages.append(ctx.new_page())

                # Navigate each active tab to its URL in place.
                for i, url in enumerate(urls):
                    try:
                        pages[i].goto(url, wait_until="domcontentloaded", timeout=10000)
                    except Exception:
                        pass

                # Clear any extra tabs left over from a larger previous batch.
                for i in range(len(urls), len(pages)):
                    try:
                        pages[i].goto("about:blank")
                    except Exception:
                        pass

            browser.close()
