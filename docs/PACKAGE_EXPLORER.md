# ROS 2 Package Explorer

Package Explorer is a read-only workspace browser and architecture canvas. It discovers packages from `package.xml`, builds declared dependency relationships, inventories source and configuration files, and statically inspects Python and XML launch files. It never imports packages or executes launch code.

## Configure and use

For normal use, select **Add workspace** in Package Explorer. The authenticated folder browser shows directories on the computer running the backend, validates that the selected folder contains at least one ROS package, and saves it in `config/workspace_roots.json`. It then opens the workspace immediately. This works when the browser is on another computer because the folders belong to the backend host.

Administrators and headless installations can also authorize roots in `config/studio.toml`:

```toml
[workspaces]
roots = ["~/ros2_ws", "/opt/ros/humble/share"]
```

`STUDIO_WORKSPACE_ROOTS` can override the configured list with paths separated by the platform path separator. Restart the backend after changing those settings. Requested paths are resolved before access and must remain inside an authorized root. Added roots persist across restarts; override their file with `STUDIO_WORKSPACE_ROOTS_FILE` when required.

The left panel contains the package and file tree. Selecting a package, file, or graph edge opens metadata or evidence in the Details dock. The center canvas supports pan, zoom, box selection, node dragging, search focus, automatic left-to-right or top-to-bottom layout, a minimap, full screen, and PNG/SVG export. Workspace mode also supports named visual groups. **Save layout** persists the current mode, positions, viewport, and groups under `config/package_layouts/`.

## Graph modes

- **Dependencies** shows workspace package dependencies and optionally unresolved external dependencies. Edge evidence points to `package.xml`.
- **Workspace** shows custom visual groups around the static package graph.
- **Launch** shows statically detected launch declarations and includes. Dynamic Python expressions remain marked unresolved.
- **Live ROS** uses the existing agent discovery data for nodes, topics, publishers, subscribers, and services.
- **Static vs live** overlays launch declarations with runtime nodes. A matching name or executable is labelled as a heuristic, not as confirmed ownership.

Python launch analysis uses the abstract syntax tree. XML launch analysis uses an XML parser. YAML launch files are inventoried but their executable relationships are not inferred. Live action endpoints are displayed without fabricated node ownership when the ROS graph does not provide that relationship.

## Architecture and limits

`backend/package_explorer/analyzer.py` owns discovery, parsing, stable identifiers, file classification, launch analysis, dependency cycles, and guarded source reads. `backend/api/package_explorer.py` exposes authenticated scan, source, root, and layout endpoints. `frontend/src/pages/PackageExplorerPage.tsx` composes the tree, source viewer, inspector, and React Flow canvas; `frontend/src/packageExplorer/` holds reusable node and layout code.

Scans skip common build, install, log, VCS, virtual-environment, and dependency directories; do not follow directory symlinks; cap discovery at 1,000 packages and 3,000 files per package; and reject binary or source files over 2 MiB. Scanning runs outside the request event loop. Large live graphs are limited to detail requests for the first 250 discovered nodes.

## Verification

Backend tests cover empty and nested workspaces, mixed CMake/Python packages, dependencies and reverse dependencies, external packages, cycles, malformed manifests, safe launch parsing, stable IDs, path traversal, symlinks, binary files, authentication, and layout persistence. The frontend production build validates TypeScript integration and bundle splitting. Run the standard commands from the repository README to repeat these checks.
