

import { type FC, useState } from "react";
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import python from 'react-syntax-highlighter/dist/esm/languages/prism/python';
import bash from 'react-syntax-highlighter/dist/esm/languages/prism/bash';
import json from 'react-syntax-highlighter/dist/esm/languages/prism/json';
import javascript from 'react-syntax-highlighter/dist/esm/languages/prism/javascript';
import typescript from 'react-syntax-highlighter/dist/esm/languages/prism/typescript';

SyntaxHighlighter.registerLanguage('python', python);
SyntaxHighlighter.registerLanguage('bash', bash);
SyntaxHighlighter.registerLanguage('json', json);
SyntaxHighlighter.registerLanguage('javascript', javascript);
SyntaxHighlighter.registerLanguage('typescript', typescript);
import {
	Copy01Icon,
	Download01Icon,
	Tick02Icon,
} from "@/components/icons";
import { cn } from "@/lib/utils";

// Devicon class mapping for language icons
const deviconMap: Record<string, string> = {
	javascript: "devicon-javascript-plain colored",
	js: "devicon-javascript-plain colored",
	typescript: "devicon-typescript-plain colored",
	ts: "devicon-typescript-plain colored",
	tsx: "devicon-react-original colored",
	jsx: "devicon-react-original colored",
	python: "devicon-python-plain colored",
	py: "devicon-python-plain colored",
	java: "devicon-java-plain colored",
	cpp: "devicon-cplusplus-plain colored",
	c: "devicon-c-plain colored",
	csharp: "devicon-csharp-plain colored",
	cs: "devicon-csharp-plain colored",
	ruby: "devicon-ruby-plain colored",
	rb: "devicon-ruby-plain colored",
	go: "devicon-go-original-wordmark colored",
	rust: "devicon-rust-original colored",
	rs: "devicon-rust-original colored",
	php: "devicon-php-plain colored",
	swift: "devicon-swift-plain colored",
	kotlin: "devicon-kotlin-plain colored",
	kt: "devicon-kotlin-plain colored",
	html: "devicon-html5-plain colored",
	css: "devicon-css3-plain colored",
	json: "devicon-json-plain colored",
	xml: "devicon-xml-plain colored",
	yaml: "devicon-yaml-plain colored",
	yml: "devicon-yaml-plain colored",
	markdown: "devicon-markdown-original",
	md: "devicon-markdown-original",
	bash: "devicon-bash-plain colored",
	shell: "devicon-bash-plain colored",
	sh: "devicon-bash-plain colored",
	sql: "devicon-mysql-plain colored",
	docker: "devicon-docker-plain colored",
	dockerfile: "devicon-docker-plain colored",
	react: "devicon-react-original colored",
	vue: "devicon-vuejs-plain colored",
	angular: "devicon-angularjs-plain colored",
	svelte: "devicon-svelte-plain colored",
	nodejs: "devicon-nodejs-plain colored",
};

// Map common language names to Prism-supported languages
const languageMap: Record<string, string> = {
	javascript: "javascript",
	js: "javascript",
	typescript: "typescript",
	ts: "typescript",
	tsx: "tsx",
	jsx: "jsx",
	python: "python",
	py: "python",
	java: "java",
	cpp: "cpp",
	c: "c",
	csharp: "csharp",
	cs: "csharp",
	ruby: "ruby",
	rb: "ruby",
	go: "go",
	rust: "rust",
	rs: "rust",
	php: "php",
	swift: "swift",
	kotlin: "kotlin",
	kt: "kotlin",
	html: "html",
	css: "css",
	json: "json",
	xml: "xml",
	yaml: "yaml",
	yml: "yaml",
	markdown: "markdown",
	md: "markdown",
	bash: "bash",
	shell: "bash",
	sh: "bash",
	sql: "sql",
};

export interface CodeBlockProps {
	children: string;
	language?: string;
	filename?: string;
	showLineNumbers?: boolean;
	className?: string;
}

export const CodeBlock: FC<CodeBlockProps> = ({
	children,
	language = "plaintext",
	filename,
	showLineNumbers = false,
	className,
}) => {
	const [copied, setCopied] = useState(false);

	const hasCode = children.trim().length > 0;
	const mappedLang = languageMap[language.toLowerCase()] || "text";

	const handleCopy = async () => {
		if (!hasCode) return;
		await navigator.clipboard.writeText(children);
		setCopied(true);
		setTimeout(() => setCopied(false), 2000);
	};

	const handleDownload = () => {
		if (!hasCode) return;

		// Generate descriptive filename
		const extension = getFileExtension(language);
		const timestamp = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
		const defaultFilename = filename || `codegen_${timestamp}.${extension}`;

		const blob = new Blob([children], { type: "text/plain" });
		const url = URL.createObjectURL(blob);
		const a = document.createElement("a");
		a.href = url;
		a.download = defaultFilename;
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(url);
	};

	const deviconClass =
		deviconMap[language.toLowerCase()] || deviconMap[language];

	return (
		<div
			className={cn(
				"relative mt-0 mx-3 rounded-xl overflow-hidden border border-border",
				"bg-background-elevated flex flex-col h-full",
				className,
			)}
		>
			{/* Header */}
			<div
				className={cn(
					"flex items-center justify-between px-4 py-2",
					"bg-muted border-b border-border",
				)}
			>
				<div className="flex items-center gap-2">
					{deviconClass ? (
						<i className={cn(deviconClass, "text-lg")} aria-hidden="true" />
					) : (
						<span
							className={cn(
								"rounded px-2 py-0.5 text-[14px] leading-relaxed",
								"bg-background text-text-muted border border-border",
							)}
						>
							{language}
						</span>
					)}
					{filename && (
						<span className="text-[14px] leading-relaxed font-normal text-text-primary">
							{filename}
						</span>
					)}
				</div>
				<div className="flex items-center gap-1">
					<button
						type="button"
						onClick={handleDownload}
						disabled={!hasCode}
						className={cn(
							"rounded-lg p-1.5 transition-all duration-150",
							hasCode
								? "cursor-pointer text-muted-foreground hover:text-foreground hover:bg-accent"
								: "cursor-not-allowed opacity-30 text-muted-foreground",
						)}
						aria-label="Download code"
					>
						<Download01Icon size={16} />
					</button>
					<button
						type="button"
						onClick={handleCopy}
						disabled={!hasCode}
						className={cn(
							"rounded-lg p-1.5 transition-all duration-150",
							hasCode
								? "cursor-pointer text-muted-foreground hover:text-foreground hover:bg-accent"
								: "cursor-not-allowed opacity-30 text-muted-foreground",
						)}
						aria-label="Copy code"
					>
						{copied ? (
							<Tick02Icon
								size={16}
								className="text-codegen"
							/>
						) : (
							<Copy01Icon size={16} />
						)}
					</button>
				</div>
			</div>

			{/* Code content */}
			<div className="flex-1 overflow-auto">
				{!hasCode ? (
					<div className="flex flex-col items-center justify-center h-full p-8">
						<div className="w-24 h-24 text-white/10 mb-4">
							<svg viewBox="0 0 400 400" className="w-full h-full" fill="none" stroke="currentColor" strokeWidth="12" strokeLinecap="round" strokeLinejoin="round">
								<path d="M 170 110 Q 150 110 140 120 Q 130 130 130 150 L 130 185 Q 130 195 120 195 L 110 195 L 110 205 L 120 205 Q 130 205 130 215 L 130 250 Q 130 270 140 280 Q 150 290 170 290" />
								<path d="M 230 110 Q 250 110 260 120 Q 270 130 270 150 L 270 185 Q 270 195 280 195 L 290 195 L 290 205 L 280 205 Q 270 205 270 215 L 270 250 Q 270 270 260 280 Q 250 290 230 290" />
								<circle cx="185" cy="200" r="5" fill="currentColor" stroke="none" />
								<circle cx="200" cy="200" r="5" fill="currentColor" stroke="none" />
								<circle cx="215" cy="200" r="5" fill="currentColor" stroke="none" />
							</svg>
						</div>
						<p className="text-sm text-white/30 text-center">
							Click the play button to start recording
						</p>
						<p className="text-xs text-white/20 text-center mt-2">
							Refresh the page if interactions aren't being captured
						</p>
					</div>
				) : (
					<SyntaxHighlighter
						language={mappedLang}
						style={vscDarkPlus}
						showLineNumbers={showLineNumbers}
						wrapLongLines
						customStyle={{
							margin: 0,
							padding: '1rem',
							background: 'transparent',
							fontSize: '14px',
							lineHeight: '1.5',
							overflowX: 'hidden',
							wordBreak: 'break-all',
						}}
						codeTagProps={{
							style: {
								fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
							}
						}}
					>
						{children}
					</SyntaxHighlighter>
				)}
			</div>
		</div>
	);
};

// Helper function to get file extension from language
function getFileExtension(language: string): string {
	const extensionMap: Record<string, string> = {
		javascript: "js",
		typescript: "ts",
		python: "py",
		java: "java",
		cpp: "cpp",
		c: "c",
		csharp: "cs",
		ruby: "rb",
		go: "go",
		rust: "rs",
		php: "php",
		swift: "swift",
		kotlin: "kt",
		html: "html",
		css: "css",
		json: "json",
		xml: "xml",
		yaml: "yaml",
		markdown: "md",
		bash: "sh",
		shell: "sh",
		sql: "sql",
	};

	return extensionMap[language.toLowerCase()] || "txt";
}
