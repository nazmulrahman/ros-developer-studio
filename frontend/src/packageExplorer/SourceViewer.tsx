import type { SourceFile } from "./types";

function tokens(line: string, language: string) {
  if (!line) return "\u00a0";
  const pattern = language === "python" ? /(#[^#]*$|\b(?:def|class|from|import|return|if|else|elif|for|while|in|as|True|False|None)\b|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g
    : language === "cpp" ? /(\/\/.*$|\b(?:class|struct|namespace|void|int|double|float|bool|auto|const|return|if|else|for|while|public|private|protected)\b|"(?:[^"\\]|\\.)*")/g
    : language === "xml" ? /(<\/?[\w:-]+|\/?>|\b[\w:-]+(?==))/g
    : /("(?:[^"\\]|\\.)*"|\b(?:true|false|null)\b|#[^#]*$)/g;
  const parts = line.split(pattern);
  return parts.map((part, i) => {
    const kind = /^#|^\/\//.test(part) ? "comment" : /^(?:def|class|from|import|return|if|else|elif|for|while|in|as|True|False|None|class|struct|namespace|void|int|double|float|bool|auto|const|public|private|protected|true|false|null)$/.test(part) ? "keyword" : /^['"]/.test(part) ? "string" : /^<|^\/?\>$/.test(part) ? "tag" : "";
    return kind ? <span key={i} className={`syntax-${kind}`}>{part}</span> : part;
  });
}

export function SourceViewer({ file, focusLine }: { file: SourceFile; focusLine?: number }) {
  return <div className="source-viewer"><div className="source-head"><span className="mono">{file.path}</span><span>{file.language} · {(file.size / 1024).toFixed(1)} KiB · read only</span></div>
    <div className="source-code">{file.content.split("\n").map((line, i) => <div key={i} className={`source-line ${focusLine === i + 1 ? "focus" : ""}`}><span className="line-no">{i + 1}</span><code>{tokens(line, file.language)}</code></div>)}</div></div>;
}
