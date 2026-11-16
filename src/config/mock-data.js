/**
 * REFERENCE & PLACEHOLDER SCIENTIFIC DATA
 * ============================================================================
 * IMPORTANT: The values below are reference placeholder datasets used to
 * validate the visual structure of the scientific telemetry panel in Phase 1.
 * None of the entries below should be interpreted as live sensor readings
 * or Artificial Intelligence analysis output.
 * ============================================================================
 */

export const PLACEHOLDER_SCIENTIFIC_DATA = Object.freeze({
  noticeBanner: 'DEMONSTRATION DATA (PLACEHOLDER) — NO LIVE API/AI INTEGRATION IN THIS STAGE',
  profiles: Object.freeze({
    earth_default: Object.freeze({
      id: 'earth_default',
      targetBadge: 'TERRESTRIAL TARGET // ANALOG REFERENCE',
      selectedTarget: {
        name: 'Planet Earth — Demonstration Site (Atacama)',
        classification: 'Terrestrial Hyperarid Environment (Placeholder)',
        biomeContext: 'Coastal Desert & Volcanic Altiplano [Synthetic Data]'
      },
      coordinates: {
        latitude: '23° 51\' 48" S',
        longitude: '69° 07\' 58" W',
        elevation: '2,450 m (Placeholder)',
        datum: 'WGS84 / EPSG:4326'
      },
      environmentalIndicators: {
        solarIrradiance: '1,361 W/m² [Placeholder]',
        atmosphericPressure: '76.4 kPa (High Altitude) [Placeholder]',
        uvIndex: '14+ Extreme [Synthetic Data]',
        relativeHumidity: '8.5% (Hyperarid) [Placeholder]'
      },
      topography: {
        reliefType: 'Endorheic basins, salt flats (salars), and volcanic cones [Placeholder]',
        averageSlope: '6.4° (Plains) to 24.0° (Escarpments) [Synthetic]',
        roughnessIndex: '0.42 TRI — Moderate Terrain Ruggedness [Placeholder]'
      },
      geology: {
        lithology: 'Andesitic basalts, evaporites, and saline crusts [Placeholder]',
        soilComposition: 'Anhydrous silicates, sulfates, and perchlorates [Demonstration]',
        stratigraphy: 'Cenozoic lacustrine sediments over volcanic basement [Placeholder]'
      },
      temperature: {
        meanAnnual: '+14.2 °C [Demonstration]',
        diurnalRange: '-8.0 °C to +31.5 °C [Placeholder]',
        surfaceThermalInertia: '1,850 J m⁻² K⁻¹ s⁻½ [Synthetic Data]'
      },
      waterAndIce: {
        surfaceWater: 'Absent / Episodic ephemeral drainage [Placeholder]',
        subsurfaceIce: 'Discontinuous permafrost above 5,200 m [Demonstration]',
        hydrologicalRegime: 'Potential evaporation > 50x precipitation [Placeholder]'
      },
      planetaryComparison: {
        lunarAnalogScore: '74% [Placeholder]',
        lunarRelevance:
          'Basaltic lava field morphology and absence of vegetation cover suitable for lunar rover mobility and optical sensor testing (Demonstration Text).',
        martianAnalogScore: '92% [Placeholder]',
        martianRelevance:
          'Hyperarid oxidized soils, sulfate/perchlorate mineralogy, and low surface biological activity analogous to Martian plains (Demonstration Text).'
      }
    }),

    moon_reference: Object.freeze({
      id: 'moon_reference',
      targetBadge: 'REFERENCE CELESTIAL BODY // MOON',
      selectedTarget: {
        name: 'Moon (Luna) — Reference Parameters',
        classification: 'Rocky Natural Satellite (Placeholder)',
        biomeContext: 'Airless Regolith Surface [Demonstration Data]'
      },
      coordinates: {
        latitude: '00° 40\' 26" N',
        longitude: '23° 28\' 22" E',
        elevation: '-1,850 m (Mare Tranquillitatis - Placeholder)',
        datum: 'Selenocentric (IAU Mean Earth/Polar Axis — LOLA)'
      },
      environmentalIndicators: {
        solarIrradiance: '1,361 W/m² (Unfiltered solar flux) [Placeholder]',
        atmosphericPressure: '~3 × 10⁻¹⁵ bar (Surface exosphere) [Placeholder]',
        uvIndex: 'Unattenuated direct solar UV incidence [Demonstration]',
        relativeHumidity: '0% (Hard surface vacuum) [Placeholder]'
      },
      topography: {
        reliefType: 'Impact craters, basaltic maria, and anorthositic highlands [Placeholder]',
        averageSlope: '2.5° (Maria) to 28.0° (Crater rims) [Synthetic]',
        roughnessIndex: 'High terrain ruggedness across highland megaregolith [Placeholder]'
      },
      geology: {
        lithology: 'Mare basalts (Maria) and anorthosites (Highlands) [Placeholder]',
        soilComposition: 'Fine abrasive regolith, glass agglutinates, and ilmenite [Demonstration]',
        stratigraphy: 'Impact-gardened megaregolith over fractured crust [Placeholder]'
      },
      temperature: {
        meanAnnual: '-23 °C (Equatorial mean) [Demonstration]',
        diurnalRange: '-173 °C (Lunar night) to +127 °C (Lunar day) [Placeholder]',
        surfaceThermalInertia: 'Low (Thermally insulating regolith layer) [Placeholder]'
      },
      waterAndIce: {
        surfaceWater: 'Absent at equatorial latitudes [Placeholder]',
        subsurfaceIce: 'Water-ice deposits in permanently shadowed polar craters (PSRs) [Demonstration]',
        hydrologicalRegime: 'Ballistic exospheric volatile transport [Placeholder]'
      },
      planetaryComparison: {
        lunarAnalogScore: '100% [Baseline Reference]',
        lunarRelevance:
          'Baseline selenological reference parameters for topographic similarity comparison against terrestrial volcanic analog regions (e.g., Craters of the Moon, Lanzarote, Hawaii) [Placeholder].',
        martianAnalogScore: 'N/A [Lunar Body]',
        martianRelevance:
          'Shares impact cratering mechanics and early basaltic volcanism processes with Mars [Demonstration Text].'
      }
    }),

    mars_reference: Object.freeze({
      id: 'mars_reference',
      targetBadge: 'REFERENCE CELESTIAL BODY // MARS',
      selectedTarget: {
        name: 'Mars — Reference Parameters',
        classification: 'Rocky Terrestrial Planet (Placeholder)',
        biomeContext: 'Arid Cryosphere with Thin CO₂ Atmosphere [Demonstration]'
      },
      coordinates: {
        latitude: '18° 22\' 48" N',
        longitude: '77° 34\' 48" E',
        elevation: '-2,500 m (Jezero Crater Ref. - Placeholder)',
        datum: 'Areocentric (MOLA Reference Sphere / Areoid)'
      },
      environmentalIndicators: {
        solarIrradiance: '590 W/m² (Top of Atmosphere) [Placeholder]',
        atmosphericPressure: '0.636 kPa (~6.36 mbar) [Placeholder]',
        uvIndex: 'High (UVC/UVB reaches surface) [Demonstration]',
        relativeHumidity: 'Variable (Nocturnal saturation of trace water vapor) [Placeholder]'
      },
      topography: {
        reliefType: 'Paleodeltas, tectonic canyons, and volcanic shields [Placeholder]',
        averageSlope: '3.8° to 21.0° [Synthetic Data]',
        roughnessIndex: 'Moderate to High Terrain Ruggedness (Boulder fields) [Placeholder]'
      },
      geology: {
        lithology: 'Iron-rich basalts, phyllosilicates (clays), and carbonates [Placeholder]',
        soilComposition: 'Oxidized regolith (hematite/magnetite), sulfates, and perchlorates [Demonstration]',
        stratigraphy: 'Noachian/Hesperian fluvio-lacustrine sequences [Placeholder]'
      },
      temperature: {
        meanAnnual: '-63 °C [Demonstration]',
        diurnalRange: '-110 °C to +20 °C [Placeholder]',
        surfaceThermalInertia: 'Moderate to Low [Synthetic Data]'
      },
      waterAndIce: {
        surfaceWater: 'Polar ice caps (H₂O and CO₂); transient brines under investigation [Placeholder]',
        subsurfaceIce: 'Mid-to-high latitude subsurface ice sheets [Demonstration]',
        hydrologicalRegime: 'Active ancient paleohydrology; modern cryosphere [Placeholder]'
      },
      planetaryComparison: {
        lunarAnalogScore: 'N/A [Martian Body]',
        lunarRelevance:
          'Basaltic volcanic provinces exhibit geotechnical parallels with lunar maria [Demonstration Text].',
        martianAnalogScore: '100% [Baseline Reference]',
        martianRelevance:
          'Baseline areological reference parameters for topographic similarity comparison against hyperarid and polar terrestrial analog regions (Atacama, McMurdo Dry Valleys, Devon Island) [Placeholder].'
      }
    })
  })
});
