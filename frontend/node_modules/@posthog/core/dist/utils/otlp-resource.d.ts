/**
 * Shape the logs and metrics resolved configs share for resource
 * attribution. Generic over the attribute value type so each signal keeps its
 * own value union.
 */
export interface OtlpResourceConfig<TAttributeValue> {
    serviceName?: string;
    serviceVersion?: string;
    environment?: string;
    resourceAttributes?: Record<string, TAttributeValue>;
}
/**
 * OTLP resource attributes shared by the logs and metrics envelopes.
 *
 * User `resourceAttributes` are spread first, then SDK-controlled keys on top so
 * a stray user key can't clobber the ingestion-attribution ones; the dedicated
 * `serviceName` / `environment` / `serviceVersion` fields are how you override
 * those three.
 *
 * @internal Shared within this SDK; not part of the stable public API.
 */
export declare function buildOtlpResourceAttributes<TAttributeValue>(config: OtlpResourceConfig<TAttributeValue>, sdkName: string, sdkVersion: string): Record<string, TAttributeValue | string>;
/**
 * Normalizes a natively-detected OS name against the table above.
 * Unrecognized names pass through: a wrong-looking value beats dropping an OS
 * we have not mapped yet.
 *
 * @internal Shared within this SDK; not part of the stable public API.
 */
export declare function normalizeOsName(name: string | undefined): string | undefined;
/**
 * The `os.name` / `os.version` resource attribute pair, with either key omitted
 * rather than emitted empty when the host cannot determine it.
 *
 * @internal Exposed for cross-package use within this SDK; not part of the stable public API.
 */
export declare function osResourceAttributes(name: string | undefined, version: string | undefined): Record<string, string>;
//# sourceMappingURL=otlp-resource.d.ts.map