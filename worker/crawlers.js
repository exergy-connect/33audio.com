// Store only a fixed crawler label and surface; never raw user agents or visitor IPs.
export const crawlers = ["Googlebot", "Bingbot", "GPTBot", "ClaudeBot", "PerplexityBot"];
export const discoveryFiles = ["/llms.txt", "/llms-full.txt", "/catalog.json", "/catalog.md"];

export function crawlerEvent(request, response, host) {
  const url = new URL(request.url);
  if (url.hostname !== host || !["GET", "HEAD"].includes(request.method) || response.status < 200 || response.status >= 400) return null;
  const surface = discoveryFiles.includes(url.pathname) ? "llms" : /^\/parts\/[^/]+\/(?:index\.html)?$/.test(url.pathname) ? "pages" : null;
  if (!surface) return null;
  const ua = (request.headers.get("User-Agent") ?? "").toLowerCase();
  const crawler = crawlers.find(name => ua.includes(name.toLowerCase()));
  return crawler ? { blobs: [crawler, surface, host], doubles: [1], indexes: [crawler] } : null;
}
