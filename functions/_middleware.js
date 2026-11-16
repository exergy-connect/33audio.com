import { crawlerEvent } from "../worker/crawlers.js";

export async function onRequest({ request, env, next }) {
  const response = await next();
  if (env.CRAWLER_EVENTS) {
    const event = crawlerEvent(request, response, env.CRAWLER_HOST ?? "33audio-com.pages.dev");
    if (event) {
      try {
        env.CRAWLER_EVENTS.writeDataPoint(event);
      } catch {
        console.error("crawler analytics write failed");
      }
    }
  }
  return response;
}
