# Resolve 21.1 release evidence

Checked 2026-09-08. This records release/API evidence; the companion impact assessment maps it to tracker code.

## Release notes supplied by the user

The attached Blackmagic forum announcement, attributed to Peter Chamberlain and dated September 8, 2026, states that advanced scripting and Python scripting now require Studio, console scripting has built-in Python, Python 2 support is removed, and a native MCP server enables interaction with AI assistants. It also lists expanded editing, rendering, transcription, and project-preset APIs.

Source: [supplied announcement](C:/Users/User/.codex/attachments/d71c4603-2d5d-416f-8e78-e06a987a9ada/pasted-text.txt). Its [official download link](https://www.blackmagicdesign.com/support/family/davinci-resolve-and-fusion) was reachable, but the retrieved page did not expose the release text. The [official forum](https://forum.blackmagicdesign.com/viewforum.php?f=21) returned HTTP 403. Therefore the exact release wording is supported by the user's attachment, not independently retrieved forum content.

## Native API evidence from this session

The main agent inspected the connected native Resolve MCP tools:

- `get_resolve_status` reported Resolve 21.1 running.
- `search_scripting_api` documented the existing tracker calls without a required migration.
- Searches of the main API stub found no idle, callback, subscription, or playback-state API. This is a search result with limited coverage, not proof that every native capability lacks events.
- `get_whats_new` queried since 21.0 only returned changes through 21.0.4. Its change list currently lags the running version.
- The MCP `run_script` sandbox uses Python 3.14; the tracker currently declares Python below 3.14. Moving the tracker into that sandbox would require separate compatibility work.

## Conclusions supported by that evidence

The Studio restriction is the direct compatibility concern for any tracker path that relies on Python scripting in free Resolve. The release notes do not establish how every existing Lua/menu-script entry point behaves, so those paths need a version-specific test before promising free-edition compatibility.

Built-in Python is described specifically for console scripting. That statement does not remove the tracker's external Python runtime or packaging requirements. A native MCP script sandbox is also a separate execution environment, not evidence that the existing desktop application can run there unchanged.

Native MCP offers a useful route for inspecting Resolve and testing API calls. Its presence alone does not provide human-activity telemetry, accurate idle detection, session persistence, or an automatic replacement for the tracker's polling loop. No verified notification contract was found in this assessment.

The added editing/rendering APIs do not themselves measure time spent editing. Transcription timing and clip/timeline timing describe media, not elapsed human work.

## Documentation freshness

Context7 selected `/websites/extremraym_cloud_resolve-scripting-doc` for the Resolve API and queried runtime requirements and native MCP behavior. Its returned prerequisites still include Python 2.7 and its edition description discusses shared Free/Studio API access. Those results conflict with the supplied 21.1 changes and cannot establish current compatibility. [Retrieved mirror](https://extremraym.com/cloud/resolve-scripting-doc).

Prefer installed 21.1 API definitions and a live connection check for compatibility decisions. No tracker code was changed for this evidence review.
