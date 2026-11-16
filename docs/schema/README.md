# 33audio catalog vocabulary

Generated from [`model/audio33-catalog.yang`](audio33-catalog.yang) with [xYang](https://github.com/exergy-connect/xYang). Do not edit by hand; run `python -m catalog schema`.

- JSON Schema (2020-12, with `x-yang`): [https://caddock-33audio.pages.dev/schema/catalog.schema.json](https://caddock-33audio.pages.dev/schema/catalog.schema.json)
- JSON-LD context: [https://caddock-33audio.pages.dev/schema/context.jsonld](https://caddock-33audio.pages.dev/schema/context.jsonld)
- Term descriptions with schema.org and Wikidata links: [https://caddock-33audio.pages.dev/schema/vocab.jsonld](https://caddock-33audio.pages.dev/schema/vocab.jsonld)
- Catalog that follows this model: [https://caddock-33audio.pages.dev/catalog.json](https://caddock-33audio.pages.dev/catalog.json)
- Source listing model (for `data/catalog.json` in the repository): [source-listing.schema.json](https://caddock-33audio.pages.dev/schema/source-listing.schema.json)

`catalog.json` carries `$schema` and `@context` pointing here. JSON-LD readers map its keys to schema.org where a property clearly matches, and to the `c33:` namespace otherwise. Terms are scoped by position, so `name` under `seller` is `schema:name` while `name` under `series` is `schema:model`.

| Path | Meaning | schema.org | Wikidata | Unit |
| --- | --- | --- | --- | --- |
| `/currency` | Currency of every price in this document. | [priceCurrency](https://schema.org/priceCurrency) |  |  |
| `/unit_price` | Listing price per resistor, the same for every part. | [price](https://schema.org/price) |  |  |
| `/region_note` | Where 33audio sells, quoted from the listing. | [eligibleRegion](https://schema.org/eligibleRegion) |  |  |
| `/provenance` | Where the stock came from, quoted from the listing. |  |  |  |
| `/source_url` | The 33audio page this catalog was parsed from. | [isBasedOn](https://schema.org/isBasedOn) |  |  |
| `/seller` | The business selling the parts. | [seller](https://schema.org/seller), class [Organization](https://schema.org/Organization) |  |  |
| `/seller/name` | Business name. | [name](https://schema.org/name) |  |  |
| `/seller/email` | Contact and order email. | [email](https://schema.org/email) |  |  |
| `/seller/locality` | City the parts ship from. | [addressLocality](https://schema.org/addressLocality) |  |  |
| `/seller/region` | State the parts ship from. | [addressRegion](https://schema.org/addressRegion) |  |  |
| `/seller/country` | ISO 3166-1 alpha-2 country code of the seller. | [addressCountry](https://schema.org/addressCountry) |  |  |
| `/seller/ebay_store` | 33audio's eBay store front. | [sameAs](https://schema.org/sameAs) |  |  |
| `/seller/ebay_seller` | eBay seller user name. | [alternateName](https://schema.org/alternateName) |  |  |
| `/shipping` | Shipping terms for an order. | [shippingDetails](https://schema.org/shippingDetails), class [OfferShippingDetails](https://schema.org/OfferShippingDetails) |  |  |
| `/shipping/amount` | Shipping charge per order. | [shippingRate](https://schema.org/shippingRate) |  |  |
| `/shipping/currency` | Currency of the shipping charge. | [currency](https://schema.org/currency) |  |  |
| `/shipping/per` | What the shipping charge covers. |  |  |  |
| `/shipping/country` | ISO 3166-1 alpha-2 code of the only shipping destination. | [shippingDestination](https://schema.org/shippingDestination) |  |  |
| `/shipping/summary` | The shipping terms as one sentence. | [description](https://schema.org/description) |  |  |
| `/series` | Caddock models in the catalog, with ratings from Caddock datasheets. | class [ProductModel](https://schema.org/ProductModel) |  |  |
| `/series/name` | Caddock model number. | [model](https://schema.org/model) |  |  |
| `/series/family` | Caddock resistor type. |  |  |  |
| `/series/product_line` | Caddock product line name for this type, as on the datasheet. | [category](https://schema.org/category) |  |  |
| `/series/film` | Resistance film named on the Caddock datasheets. |  |  |  |
| `/series/power_rating` | Rated power in watts at +25 C from the Caddock datasheet. MS models are rated the same at +125 C. |  | [Q25236](https://www.wikidata.org/wiki/Q25236) | WTT |
| `/series/voltage_rating` | Maximum continuous working voltage from the Caddock datasheet. |  | [Q25250](https://www.wikidata.org/wiki/Q25250) | VLT |
| `/series/default_tolerance` | Tolerance of a part in this series unless its part number adds a letter. |  |  |  |
| `/series/not_recommended_for_new_designs` | True when Caddock marks the type Not Recommended for New Designs. Caddock says this of Type MM. |  |  |  |
| `/series/datasheet` | Link to the datasheet these ratings come from. | [subjectOf](https://schema.org/subjectOf) |  |  |
| `/parts` | One stocked resistor value. | [itemListElement](https://schema.org/itemListElement), class [Product](https://schema.org/Product) | [Q5321](https://www.wikidata.org/wiki/Q5321) |  |
| `/parts/part_number` | 33audio part id: series, resistance, and a tolerance letter only when the listing marks one, such as MM177-4.32K or MM177-665K-F. | [mpn](https://schema.org/mpn) |  |  |
| `/parts/manufacturer` | Resistor manufacturer. | [manufacturer](https://schema.org/manufacturer) |  |  |
| `/parts/series` | The Caddock model this part belongs to. | [model](https://schema.org/model) |  |  |
| `/parts/resistance` | Nominal resistance as a number and a unit. | [additionalProperty](https://schema.org/additionalProperty), class [PropertyValue](https://schema.org/PropertyValue) | [Q25358](https://www.wikidata.org/wiki/Q25358) |  |
| `/parts/resistance/value` | Resistance in ohms. | [value](https://schema.org/value) |  |  |
| `/parts/resistance/unit` | Unit of value. Always ohm. | [unitText](https://schema.org/unitText) | [Q47083](https://www.wikidata.org/wiki/Q47083) | OHM |
| `/parts/resistance/label` | Human-readable value, such as 4.32 kΩ. | [name](https://schema.org/name) |  |  |
| `/parts/tolerance` | Resistance tolerance. | class [PropertyValue](https://schema.org/PropertyValue) | [Q950292](https://www.wikidata.org/wiki/Q950292) |  |
| `/parts/tolerance/percent` | Tolerance in percent. | [value](https://schema.org/value) |  |  |
| `/parts/tolerance/code` | Tolerance letter. |  |  |  |
| `/parts/condition` | Item condition. schema.org has no NOS value, so this links to Wikidata instead. |  | [Q907054](https://www.wikidata.org/wiki/Q907054) |  |
| `/parts/quantity` | Quantity on the 33audio listing. | [inventoryLevel](https://schema.org/inventoryLevel) |  |  |
| `/parts/price` | Price per piece. | [price](https://schema.org/price) |  |  |
| `/parts/currency` | Currency of price. | [priceCurrency](https://schema.org/priceCurrency) |  |  |
| `/parts/url` | The part's page on the 33audio catalog site. | [url](https://schema.org/url) |  |  |
| `/parts/ebay_listing` | An active eBay listing for this exact part, when one is matched. | class [Offer](https://schema.org/Offer) |  |  |

Power and voltage ratings come from Caddock's Type MM and Type MS datasheets. Prices, quantities, and condition come from the 33audio listing.
