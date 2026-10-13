export interface WorkspaceFile { path: string; name: string; kind: "launch" | "config" | "source" | "robot_description" | "metadata" | "other"; size: number }
export interface LaunchNode { package: string | null; executable: string | null; name: string | null; namespace: string | null; line?: number; evidence: string; dynamic?: boolean }
export interface LaunchAnalysis { path: string; format: string; nodes: LaunchNode[]; includes: { value: string | null; line?: number; dynamic?: boolean }[]; arguments: { name: string | null; default: string | null; line?: number }[]; warnings: string[] }
export interface PackageInfo {
  id: string; name: string; path: string; metadata_path: string; version: string | null; description: string | null;
  build_type: string; type: string; maintainers: string[]; licenses: string[]; executables: string[];
  dependencies: { name: string; kind: string; evidence: string }[]; reverse_dependencies: string[];
  files: WorkspaceFile[]; launch: LaunchAnalysis[]; warnings: string[];
}
export interface DependencyEdge { id: string; source: string; target: string; kind: string; workspace: boolean; resolved: boolean; evidence: string }
export interface WorkspaceScan {
  workspace_id: string; path: string; name: string; packages: PackageInfo[]; edges: DependencyEdge[]; external_dependencies: string[];
  summary: { packages: number; package_types: Record<string, number>; declared_dependencies: number; external_dependencies: number; launch_files: number; config_files: number; cycles: string[][]; warnings: number };
  warnings: string[];
}
export interface SavedGroup { id: string; name: string; members: string[]; collapsed: boolean; color?: string }
export interface PackageLayout { workspace_id: string; mode: GraphMode; viewport: { x?: number; y?: number; zoom?: number }; positions: Record<string, { x: number; y: number }>; groups: SavedGroup[] }
export type GraphMode = "dependencies" | "architecture" | "launch" | "live" | "comparison";
export interface SourceFile { path: string; language: string; size: number; content: string }
export interface FolderListing {
  path: string; parent: string | null;
  locations: { name: string; path: string }[];
  directories: { name: string; path: string; package: boolean }[];
}
