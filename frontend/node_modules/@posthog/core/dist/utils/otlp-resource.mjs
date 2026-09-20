function buildOtlpResourceAttributes(config, sdkName, sdkVersion) {
    return {
        ...config.resourceAttributes,
        'service.name': config.serviceName || 'unknown_service',
        ...config.environment && {
            'deployment.environment': config.environment
        },
        ...config.serviceVersion && {
            'service.version': config.serviceVersion
        },
        'telemetry.sdk.name': sdkName,
        'telemetry.sdk.version': sdkVersion
    };
}
const OS_NAMES = {
    darwin: 'macOS',
    win32: 'Windows',
    linux: 'Linux',
    android: 'Android',
    freebsd: 'FreeBSD',
    openbsd: 'OpenBSD',
    sunos: 'SunOS',
    aix: 'AIX',
    'Mac OS X': 'macOS'
};
function normalizeOsName(name) {
    if (!name) return;
    return Object.prototype.hasOwnProperty.call(OS_NAMES, name) ? OS_NAMES[name] : name;
}
function osResourceAttributes(name, version) {
    const osName = normalizeOsName(name);
    return {
        ...osName ? {
            'os.name': osName
        } : {},
        ...version ? {
            'os.version': version
        } : {}
    };
}
export { buildOtlpResourceAttributes, normalizeOsName, osResourceAttributes };
