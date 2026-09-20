import { isUndefined } from "../../utils/index.mjs";
const UNKNOWN_FUNCTION = '?';
const MASKED_URL_PREFIX = 'webkit-masked-url://';
const ANONYMOUS_FILENAME = '<anonymous>';
function createFrame(platform, filename, func, lineno, colno) {
    const frame = {
        platform,
        filename,
        function: '<anonymous>' === func ? UNKNOWN_FUNCTION : func,
        in_app: !!filename && !filename.startsWith(MASKED_URL_PREFIX) && filename !== ANONYMOUS_FILENAME
    };
    if (!isUndefined(lineno)) frame.lineno = lineno;
    if (!isUndefined(colno)) frame.colno = colno;
    return frame;
}
export { UNKNOWN_FUNCTION, createFrame };
