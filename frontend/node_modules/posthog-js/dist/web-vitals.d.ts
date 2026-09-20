/** Subset of the web-vitals library's `ReportOpts` passed to metric observers. */
interface WebVitalsReportOpts {
    reportAllChanges?: boolean;
    reportSoftNavs?: boolean;
}
type WebVitalsMetricCallbacks = {
    onLCP: (onReport: (metric: any) => void, opts?: WebVitalsReportOpts) => void;
    onCLS: (onReport: (metric: any) => void, opts?: WebVitalsReportOpts) => void;
    onFCP: (onReport: (metric: any) => void, opts?: WebVitalsReportOpts) => void;
    onINP: (onReport: (metric: any) => void, opts?: WebVitalsReportOpts) => void;
};
type WebVitalsCallbacks = WebVitalsMetricCallbacks & {
    withoutAttribution?: WebVitalsMetricCallbacks;
};

/**
 * Web Vitals entrypoint (without attribution)
 *
 * This is the lighter bundle (~6KB) that captures core web vitals metrics
 * without attribution data. Attribution data includes debugging information like
 * which elements caused layout shifts, timing breakdowns, etc.
 *
 * We split this into two bundles because:
 * 1. Attribution code adds ~6KB to the bundle size
 * 2. Attribution can cause memory issues in SPAs (onCLS holds references to detached DOM elements)
 *
 * Attribution is on by default for INP and LCP, so most pages load the attribution
 * bundle. This bundle loads only when attribution is fully disabled by setting:
 *   capture_performance: { web_vitals_attribution: false }
 *
 * @see web-vitals-with-attribution.ts
 */

declare const postHogWebVitalsCallbacks: WebVitalsCallbacks;

export { postHogWebVitalsCallbacks as default };
