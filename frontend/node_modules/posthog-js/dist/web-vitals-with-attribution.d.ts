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
 * Web Vitals entrypoint (with attribution)
 *
 * This bundle includes both attributed and unattributed observers so the SDK can
 * select attribution per metric. INP and LCP use attribution by default; CLS and
 * FCP use the unattributed observers unless explicitly configured otherwise.
 *
 * This bundle is ~18KB (vs ~6KB for the non-attribution version).
 *
 * Note: Attribution can cause memory issues in SPAs because the attributed onCLS
 * callback holds references to DOM elements that may be detached during navigation.
 *
 * Set capture_performance.web_vitals_attribution to true to attribute every metric,
 * false to load the lighter bundle, or an array to select individual metrics.
 *
 * @see web-vitals.ts for the lighter bundle
 */

declare const postHogWebVitalsCallbacks: WebVitalsCallbacks;

export { postHogWebVitalsCallbacks as default };
