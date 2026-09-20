"use strict";
var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
var __values = (this && this.__values) || function(o) {
    var s = typeof Symbol === "function" && Symbol.iterator, m = s && o[s], i = 0;
    if (m) return m.call(o);
    if (o && typeof o.length === "number") return {
        next: function () {
            if (o && i >= o.length) o = void 0;
            return { value: o && o[i++], done: !o };
        }
    };
    throw new TypeError(s ? "Object is not iterable." : "Symbol.iterator is not defined.");
};
var __read = (this && this.__read) || function (o, n) {
    var m = typeof Symbol === "function" && o[Symbol.iterator];
    if (!m) return o;
    var i = m.call(o), r, ar = [], e;
    try {
        while ((n === void 0 || n-- > 0) && !(r = i.next()).done) ar.push(r.value);
    }
    catch (error) { e = { error: error }; }
    finally {
        try {
            if (r && !r.done && (m = i["return"])) m.call(i);
        }
        finally { if (e) throw e.error; }
    }
    return ar;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.JSON_LD_EVENT_TAG = void 0;
exports.sanitizeJsonLd = sanitizeJsonLd;
exports.startJsonLdCapture = startJsonLdCapture;
var core_1 = require("@posthog/core");
var MAX_JSON_LD_LENGTH = 100000;
var MAX_JSON_LD_OUTPUT_LENGTH = 20000;
var SCHEMA_CONTEXT = 'https://schema.org';
var ANY_ENTITY_TYPES = [];
var TYPE_INDEPENDENT_LEAF_PROPERTIES = 'actionStatus availability bestRating contentRating encodingFormat eventAttendanceMode eventStatus highPrice inLanguage isAccessibleForFree isFamilyFriendly itemCondition itemListOrder lowPrice maximumAttendeeCapacity nonprofitStatus numberOfItems offerCount position price priceCurrency priceValidUntil publicAccess ratingCount ratingValue reviewCount smokingAllowed worstRating'.split(' ');
var ACTION_TYPES = 'Action BorrowAction ReadAction SearchAction SeekToAction SolveMathAction WatchAction'.split(' ');
var ORGANIZATION_TYPES = 'AutoDealer Bakery BarOrPub CafeOrCoffeeShop CollegeOrUniversity Corporation DaySpa Dentist EducationalOrganization Electrician FoodEstablishment GovernmentOrganization HealthClub Hotel LegalService Library LibrarySystem LocalBusiness Locksmith LodgingBusiness MedicalBusiness NGO OnlineStore Organization PerformingGroup Pharmacy Physician Plumber RealEstateAgent Restaurant School SportsOrganization Store'.split(' ');
var PLACE_TYPES = 'Accommodation AdministrativeArea Country Place State'.split(' ');
var ENTITY_RULES = {
    AggregateOffer: {
        offers: ['Offer'],
    },
    Brand: {
        name: true,
    },
    BreadcrumbList: {
        itemListElement: ['ListItem'],
    },
    CreativeWork: {
        genre: true,
        dateCreated: true,
        dateModified: true,
        datePublished: true,
        expires: true,
        learningResourceType: true,
        educationalLevel: true,
        educationalUse: true,
        interactivityType: true,
        aggregateRating: ['AggregateRating'],
        potentialAction: ACTION_TYPES,
        publisher: ORGANIZATION_TYPES,
    },
    Event: {
        startDate: true,
        endDate: true,
        previousStartDate: true,
        aggregateRating: ['AggregateRating'],
        offers: ['AggregateOffer', 'Offer'],
    },
    ItemList: {
        itemListElement: ['ListItem'],
    },
    ListItem: {
        item: ANY_ENTITY_TYPES,
    },
    Offer: {
        seller: ORGANIZATION_TYPES,
    },
    Organization: {
        name: true,
        legalName: true,
        foundingDate: true,
        dissolutionDate: true,
        aggregateRating: ['AggregateRating'],
        brand: ['Brand'],
    },
    Person: {},
    Place: {
        aggregateRating: ['AggregateRating'],
    },
    Product: {
        name: true,
        sku: true,
        mpn: true,
        gtin: true,
        gtin8: true,
        gtin12: true,
        gtin13: true,
        gtin14: true,
        productID: true,
        productGroupID: true,
        asin: true,
        model: true,
        category: true,
        color: true,
        material: true,
        pattern: true,
        size: true,
        productionDate: true,
        releaseDate: true,
        brand: ['Brand', 'Organization'],
        manufacturer: ORGANIZATION_TYPES,
        offers: ['Offer', 'AggregateOffer'],
        aggregateRating: ['AggregateRating'],
    },
    Service: {
        name: true,
        serviceType: true,
        category: true,
        provider: ORGANIZATION_TYPES,
        areaServed: PLACE_TYPES,
        offers: ['AggregateOffer', 'Offer'],
        aggregateRating: ['AggregateRating'],
    },
    OfferCatalog: {
        name: true,
        itemListElement: ANY_ENTITY_TYPES,
    },
};
var EMPTY_ENTITY_RULES = {};
var INHERITED_RULE_GROUPS = [
    [ACTION_TYPES, EMPTY_ENTITY_RULES],
    [
        '3DModel AboutPage Answer Article AudioObject Blog BlogPosting Book Clip CollectionPage Comment ContactPage Course CreativeWorkSeason CreativeWorkSeries DataCatalog DataDownload DataFeed Dataset DiscussionForumPosting Episode FAQPage Game HowTo HowToDirection HowToSection HowToStep HowToTip ImageObject LearningResource MediaObject Message MobileApplication Movie MusicPlaylist MusicRecording NewsArticle Photograph PodcastEpisode PodcastSeries ProfilePage QAPage Question Quiz Recipe Review ScholarlyArticle SearchResultsPage SiteNavigationElement SocialMediaPosting SoftwareApplication TVEpisode TVSeries TechArticle VacationRental VideoGame VideoObject WebApplication WebPage WebPageElement WebSite'.split(' '),
        ENTITY_RULES.CreativeWork,
    ],
    [
        'BroadcastEvent BusinessEvent EducationEvent Festival MusicEvent SportsEvent TheaterEvent'.split(' '),
        ENTITY_RULES.Event,
    ],
    [ORGANIZATION_TYPES, ENTITY_RULES.Organization],
    [PLACE_TYPES, ENTITY_RULES.Place],
    ['Car IndividualProduct ProductGroup ProductModel'.split(' '), ENTITY_RULES.Product],
    ['AggregateRating EmployerAggregateRating Rating'.split(' '), EMPTY_ENTITY_RULES],
];
var TYPES_WITHOUT_PROPERTIES = 'AlignmentObject BedDetails Certification ContactPoint CreditCard DefinedRegion EducationalOccupationalCredential EntryPoint GeoCoordinates GeoShape InteractionCounter JobPosting LocationFeatureSpecification MathSolver MemberProgram MemberProgramTier MerchantReturnPolicy MerchantReturnPolicySeasonalOverride MonetaryAmount NutritionInformation OccupationalExperienceRequirements OfferShippingDetails OpeningHoursSpecification PeopleAudience PostalAddress PriceSpecification PropertyValue QuantitativeValue ServicePeriod ShippingConditions ShippingDeliveryTime ShippingRateSettings ShippingService SpeakableSpecification Thing UnitPriceSpecification'.split(' ');
exports.JSON_LD_EVENT_TAG = '$json_ld';
function getOwnProperty(value, property) {
    return core_1.hasOwnProperty.call(value, property) ? value[property] : undefined;
}
function isScalar(value) {
    var type = typeof value;
    return (0, core_1.isNull)(value) || type === 'string' || type === 'number' || type === 'boolean';
}
function sanitizeScalar(value) {
    return isScalar(value) || ((0, core_1.isArray)(value) && value.every(isScalar)) ? value : undefined;
}
function getEntityRules(type) {
    var e_1, _a;
    if (core_1.hasOwnProperty.call(ENTITY_RULES, type)) {
        return ENTITY_RULES[type];
    }
    try {
        for (var INHERITED_RULE_GROUPS_1 = __values(INHERITED_RULE_GROUPS), INHERITED_RULE_GROUPS_1_1 = INHERITED_RULE_GROUPS_1.next(); !INHERITED_RULE_GROUPS_1_1.done; INHERITED_RULE_GROUPS_1_1 = INHERITED_RULE_GROUPS_1.next()) {
            var _b = __read(INHERITED_RULE_GROUPS_1_1.value, 2), types = _b[0], rules = _b[1];
            if (types.includes(type)) {
                return rules;
            }
        }
    }
    catch (e_1_1) { e_1 = { error: e_1_1 }; }
    finally {
        try {
            if (INHERITED_RULE_GROUPS_1_1 && !INHERITED_RULE_GROUPS_1_1.done && (_a = INHERITED_RULE_GROUPS_1.return)) _a.call(INHERITED_RULE_GROUPS_1);
        }
        finally { if (e_1) throw e_1.error; }
    }
    return TYPES_WITHOUT_PROPERTIES.includes(type) ? EMPTY_ENTITY_RULES : undefined;
}
function getEntityTypes(value) {
    var values = typeof value === 'string' ? [value] : (0, core_1.isArray)(value) ? value : [];
    return values
        .filter(function (type) { return typeof type === 'string'; })
        .map(function (type) { return type.replace(/^https?:\/\/schema\.org\//, ''); })
        .filter(function (type) { return !!getEntityRules(type); });
}
function sanitizeEntity(value, allowedTypes) {
    var e_2, _a, e_3, _b, e_4, _c;
    if (!(0, core_1.isObject)(value)) {
        return null;
    }
    var typeValue = getOwnProperty(value, '@type');
    var types = getEntityTypes(typeValue).filter(function (type) { return !allowedTypes || !allowedTypes.length || allowedTypes.includes(type); });
    if (!types.length) {
        return null;
    }
    var result = { '@type': typeof typeValue === 'string' ? types[0] : types };
    var id = sanitizeScalar(getOwnProperty(value, '@id'));
    if (!(0, core_1.isUndefined)(id)) {
        result['@id'] = id;
    }
    try {
        for (var TYPE_INDEPENDENT_LEAF_PROPERTIES_1 = __values(TYPE_INDEPENDENT_LEAF_PROPERTIES), TYPE_INDEPENDENT_LEAF_PROPERTIES_1_1 = TYPE_INDEPENDENT_LEAF_PROPERTIES_1.next(); !TYPE_INDEPENDENT_LEAF_PROPERTIES_1_1.done; TYPE_INDEPENDENT_LEAF_PROPERTIES_1_1 = TYPE_INDEPENDENT_LEAF_PROPERTIES_1.next()) {
            var property = TYPE_INDEPENDENT_LEAF_PROPERTIES_1_1.value;
            var scalar = sanitizeScalar(getOwnProperty(value, property));
            if (!(0, core_1.isUndefined)(scalar)) {
                result[property] = scalar;
            }
        }
    }
    catch (e_2_1) { e_2 = { error: e_2_1 }; }
    finally {
        try {
            if (TYPE_INDEPENDENT_LEAF_PROPERTIES_1_1 && !TYPE_INDEPENDENT_LEAF_PROPERTIES_1_1.done && (_a = TYPE_INDEPENDENT_LEAF_PROPERTIES_1.return)) _a.call(TYPE_INDEPENDENT_LEAF_PROPERTIES_1);
        }
        finally { if (e_2) throw e_2.error; }
    }
    try {
        for (var types_1 = __values(types), types_1_1 = types_1.next(); !types_1_1.done; types_1_1 = types_1.next()) {
            var type = types_1_1.value;
            var rules = getEntityRules(type);
            var _loop_1 = function (property) {
                var propertyValue = getOwnProperty(value, property);
                var rule = rules[property];
                if (rule === true) {
                    var scalar = sanitizeScalar(propertyValue);
                    if (!(0, core_1.isUndefined)(scalar)) {
                        result[property] = scalar;
                    }
                }
                else if ((0, core_1.isArray)(propertyValue)) {
                    var items = propertyValue.map(function (item) { return sanitizeEntity(item, rule); }).filter(core_1.isObject);
                    if (items.length) {
                        result[property] = items;
                    }
                }
                else {
                    var nestedEntity = sanitizeEntity(propertyValue, rule);
                    if (nestedEntity) {
                        result[property] = nestedEntity;
                    }
                }
            };
            try {
                for (var _d = (e_4 = void 0, __values(Object.keys(rules))), _e = _d.next(); !_e.done; _e = _d.next()) {
                    var property = _e.value;
                    _loop_1(property);
                }
            }
            catch (e_4_1) { e_4 = { error: e_4_1 }; }
            finally {
                try {
                    if (_e && !_e.done && (_c = _d.return)) _c.call(_d);
                }
                finally { if (e_4) throw e_4.error; }
            }
        }
    }
    catch (e_3_1) { e_3 = { error: e_3_1 }; }
    finally {
        try {
            if (types_1_1 && !types_1_1.done && (_b = types_1.return)) _b.call(types_1);
        }
        finally { if (e_3) throw e_3.error; }
    }
    return result;
}
function sanitizeRoot(value) {
    if (!(0, core_1.isObject)(value)) {
        return null;
    }
    var context = getOwnProperty(value, '@context');
    if (typeof context !== 'string' || !/^https?:\/\/schema\.org\/?$/.test(context)) {
        return null;
    }
    var entity = sanitizeEntity(value);
    if (entity) {
        return __assign({ '@context': SCHEMA_CONTEXT }, entity);
    }
    var graph = getOwnProperty(value, '@graph');
    if (!(0, core_1.isArray)(graph)) {
        return null;
    }
    var entities = graph.map(function (entity) { return sanitizeEntity(entity); }).filter(core_1.isObject);
    return entities.length ? { '@context': SCHEMA_CONTEXT, '@graph': entities } : null;
}
function sanitizeJsonLd(text) {
    if (!text || text.length > MAX_JSON_LD_LENGTH) {
        return null;
    }
    try {
        var value = JSON.parse(text);
        var sanitized = (0, core_1.isArray)(value) ? value.map(sanitizeRoot) : sanitizeRoot(value);
        if ((0, core_1.isNull)(sanitized) || ((0, core_1.isArray)(sanitized) && (!sanitized.length || sanitized.some(core_1.isNull)))) {
            return null;
        }
        var output = JSON.stringify(sanitized);
        return output.length <= MAX_JSON_LD_OUTPUT_LENGTH ? [sanitized, output] : null;
    }
    catch (_a) {
        return null;
    }
}
function isJsonLdScript(node) {
    var _a;
    return (node.nodeName === 'SCRIPT' &&
        ((_a = node.getAttribute('type')) === null || _a === void 0 ? void 0 : _a.trim().toLowerCase()) === 'application/ld+json');
}
function matchesPrivacyRule(element, classRule, selector) {
    if (typeof classRule === 'string'
        ? element.classList.contains(classRule)
        : classRule &&
            Array.from(element.classList).some(function (className) {
                classRule.lastIndex = 0;
                return classRule.test(className);
            })) {
        return true;
    }
    try {
        return !!selector && element.matches(selector);
    }
    catch (_a) {
        return false;
    }
}
function isWithinPrivacyBoundary(element, options) {
    for (var current = element; current;) {
        if (matchesPrivacyRule(current, options.blockClass, options.blockSelector) ||
            matchesPrivacyRule(current, options.maskTextClass, options.maskTextSelector)) {
            return true;
        }
        var parentNode = current.parentNode;
        current =
            current.parentElement ||
                (parentNode && parentNode.nodeType === parentNode.DOCUMENT_FRAGMENT_NODE
                    ? parentNode.host
                    : null);
    }
    return false;
}
function getJsonLdScripts(node) {
    if (isJsonLdScript(node)) {
        return [node];
    }
    if (node.nodeType !== node.ELEMENT_NODE) {
        return [];
    }
    return Array.from(node.querySelectorAll('script')).filter(isJsonLdScript);
}
function startJsonLdCapture(doc, MutationObserverClass, options) {
    var lastJsonByScript = new WeakMap();
    var getCaptureState = options.getCaptureState || (function () { return true; });
    var remainingLength = MAX_JSON_LD_LENGTH;
    var captureScript = function (script) {
        try {
            var captureState = getCaptureState();
            if (!remainingLength ||
                captureState === false ||
                !script.isConnected ||
                script.ownerDocument !== doc ||
                isWithinPrivacyBoundary(script, options)) {
                return;
            }
            var sanitized = sanitizeJsonLd(script.text);
            if (!sanitized) {
                lastJsonByScript.delete(script);
                return;
            }
            var _a = __read(sanitized, 2), jsonLd = _a[0], json = _a[1];
            if ((0, core_1.isNull)(captureState)) {
                lastJsonByScript.set(script, json);
                return;
            }
            if (lastJsonByScript.get(script) !== json) {
                if (json.length > remainingLength) {
                    remainingLength = 0;
                    return;
                }
                if (options.emit(jsonLd)) {
                    lastJsonByScript.set(script, json);
                    remainingLength -= json.length;
                }
            }
        }
        catch (_b) {
            return;
        }
    };
    try {
        var observer_1 = new MutationObserverClass(function (mutations) {
            var e_5, _a;
            try {
                if (!remainingLength || getCaptureState() === false) {
                    return;
                }
                var captureScripts = function (node) {
                    var e_6, _a;
                    try {
                        for (var _b = __values(getJsonLdScripts(node)), _c = _b.next(); !_c.done; _c = _b.next()) {
                            var script = _c.value;
                            captureScript(script);
                        }
                    }
                    catch (e_6_1) { e_6 = { error: e_6_1 }; }
                    finally {
                        try {
                            if (_c && !_c.done && (_a = _b.return)) _a.call(_b);
                        }
                        finally { if (e_6) throw e_6.error; }
                    }
                };
                try {
                    for (var mutations_1 = __values(mutations), mutations_1_1 = mutations_1.next(); !mutations_1_1.done; mutations_1_1 = mutations_1.next()) {
                        var mutation = mutations_1_1.value;
                        if (mutation.type === 'childList') {
                            if (isJsonLdScript(mutation.target)) {
                                captureScript(mutation.target);
                            }
                            mutation.addedNodes.forEach(captureScripts);
                        }
                        else if (mutation.type === 'characterData') {
                            var parent_1 = mutation.target.parentNode;
                            if (parent_1 && isJsonLdScript(parent_1)) {
                                captureScript(parent_1);
                            }
                        }
                        else if (mutation.type === 'attributes' && isJsonLdScript(mutation.target)) {
                            captureScript(mutation.target);
                        }
                    }
                }
                catch (e_5_1) { e_5 = { error: e_5_1 }; }
                finally {
                    try {
                        if (mutations_1_1 && !mutations_1_1.done && (_a = mutations_1.return)) _a.call(mutations_1);
                    }
                    finally { if (e_5) throw e_5.error; }
                }
            }
            catch (_b) {
                return;
            }
        });
        observer_1.observe(doc, {
            attributes: true,
            attributeFilter: ['type'],
            characterData: true,
            childList: true,
            subtree: true,
        });
        var scan = function (force) {
            if (force === void 0) { force = false; }
            if (!remainingLength || getCaptureState() === false) {
                return;
            }
            getJsonLdScripts(doc.documentElement).forEach(function (script) {
                if (force) {
                    lastJsonByScript.delete(script);
                }
                captureScript(script);
            });
        };
        return { scan: scan, stop: function () { return observer_1.disconnect(); } };
    }
    catch (_a) {
        return { scan: function () { }, stop: function () { } };
    }
}
//# sourceMappingURL=json-ld.js.map