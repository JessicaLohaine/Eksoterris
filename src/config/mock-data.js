/**
 * DADOS DEMONSTRATIVOS (PLACEHOLDER)
 * ============================================================================
 * IMPORTANTE: Todos os valores abaixo são estritamente demonstrativos (placeholders)
 * utilizados para validar a estrutura visual do painel científico na Fase 1.
 * Nenhuma informação aqui deve ser interpretada como leitura real de sensores
 * ou resultado de análise por Inteligência Artificial.
 * ============================================================================
 */

export const PLACEHOLDER_SCIENTIFIC_DATA = Object.freeze({
  noticeBanner: 'DADOS DEMONSTRATIVOS (PLACEHOLDER) — SEM INTEGRAÇÃO DE API/IA NESTA FASE',
  profiles: Object.freeze({
    earth_default: Object.freeze({
      id: 'earth_default',
      targetBadge: 'ALVO TERRESTRE // REFERÊNCIA DEMONSTRATIVA',
      selectedTarget: {
        name: 'Planeta Terra — Sítio Demonstrativo (Atacama)',
        classification: 'Ambiente Hiperárido Terrestre (Placeholder)',
        biomeContext: 'Deserto Costeiro e Altiplano Vulcânico [Dados Fictícios]'
      },
      coordinates: {
        latitude: '23° 51\' 48" S',
        longitude: '69° 07\' 58" W',
        elevation: '2.450 m (Placeholder)',
        datum: 'WGS84 / EPSG:4326'
      },
      environmentalIndicators: {
        solarIrradiance: '1.361 W/m² [Placeholder]',
        atmosphericPressure: '76,4 kPa (Altitude) [Placeholder]',
        uvIndex: '14+ Extremo [Dados Fictícios]',
        relativeHumidity: '8,5% (Hiperárido) [Placeholder]'
      },
      topography: {
        reliefType: 'Bacias endorreicas, salares e cones vulcânicos [Placeholder]',
        averageSlope: '6,4° (Planície) a 24,0° (Escarpa) [Fictício]',
        roughnessIndex: '0,42 IRI — Moderado [Placeholder]'
      },
      geology: {
        lithology: 'Basaltos andesíticos, evaporitos e crostas salinas [Placeholder]',
        soilComposition: 'Silicatos anidros, sulfatos e percloratos [Demonstrativo]',
        stratigraphy: 'Sedimentos lacustres cenozoicos sobre embasamento vulcânico [Placeholder]'
      },
      temperature: {
        meanAnnual: '+14,2 °C [Demonstrativo]',
        diurnalRange: '-8,0 °C a +31,5 °C [Placeholder]',
        surfaceThermalInertia: '1.850 J m⁻² K⁻¹ s⁻½ [Dados Fictícios]'
      },
      waterAndIce: {
        surfaceWater: 'Ausente / Drenagem efêmera episódica [Placeholder]',
        subsurfaceIce: 'Permafrost descontínuo acima de 5.200 m [Demonstrativo]',
        hydrologicalRegime: 'Evaporação potencial > 50x precipitação [Placeholder]'
      },
      planetaryComparison: {
        lunarAnalogScore: '74% [Placeholder]',
        lunarRelevance:
          'Morfologia de campos de lava basáltica e ausência de cobertura vegetal úteis para testes de locomoção e sensores ópticos lunares (Texto Demonstrativo).',
        martianAnalogScore: '92% [Placeholder]',
        martianRelevance:
          'Solos oxidados hiperáridos, presença de sulfatos/percloratos e baixa atividade biológica superficial análogos às planícies marcianas (Texto Demonstrativo).'
      }
    }),

    moon_reference: Object.freeze({
      id: 'moon_reference',
      targetBadge: 'CORPO CELESTE DE COMPARAÇÃO // LUA',
      selectedTarget: {
        name: 'Lua (Luna) — Parâmetros de Referência',
        classification: 'Satélite Natural Rochoso (Placeholder)',
        biomeContext: 'Superfície Regolítica Sem Atmosfera [Dados Demonstrativos]'
      },
      coordinates: {
        latitude: '00° 40\' 26" N',
        longitude: '23° 28\' 22" E',
        elevation: '-1.850 m (Mare Tranquillitatis - Placeholder)',
        datum: 'Selenocêntrico (IAU Mean Earth/Polar Axis)'
      },
      environmentalIndicators: {
        solarIrradiance: '1.361 W/m² (Sem filtragem atmosférica) [Placeholder]',
        atmosphericPressure: '~3 × 10⁻¹⁵ bar (Exosfera) [Placeholder]',
        uvIndex: 'Incidência direta não atenuada [Demonstrativo]',
        relativeHumidity: '0% (Vácuo superficial) [Placeholder]'
      },
      topography: {
        reliefType: 'Crateras de impacto, mares basálticos e terras altas [Placeholder]',
        averageSlope: '2,5° (Maria) a 28,0° (Bordas de cratera) [Fictício]',
        roughnessIndex: 'Alto em terras altas anortosíticas [Placeholder]'
      },
      geology: {
        lithology: 'Basaltos lunares (Maria) e Anortositos (Highlands) [Placeholder]',
        soilComposition: 'Regolito fino abrasivo, aglutinados vítreos e ilmenita [Demonstrativo]',
        stratigraphy: 'Megarregolito fragmentado por impactos meteoríticos [Placeholder]'
      },
      temperature: {
        meanAnnual: '-23 °C (Equador médio) [Demonstrativo]',
        diurnalRange: '-173 °C (Noite) a +127 °C (Dia) [Placeholder]',
        surfaceThermalInertia: 'Baixa (Regolito isolante térmico) [Placeholder]'
      },
      waterAndIce: {
        surfaceWater: 'Ausente em latitudes equatoriais [Placeholder]',
        subsurfaceIce: 'Depósitos de gelo em crateras permanentemente sombreadas (Polos) [Demonstrativo]',
        hydrologicalRegime: 'Transporte volátil exosférico [Placeholder]'
      },
      planetaryComparison: {
        lunarAnalogScore: '100% [Referência Base]',
        lunarRelevance:
          'Parâmetros de referência para comparação futura com campos vulcânicos terrestres (ex.: Craters of the Moon, Lanzarote, Havaí) [Placeholder].',
        martianAnalogScore: 'N/A [Corpo Lunar]',
        martianRelevance:
          'Compartilha processos de craterização por impacto e vulcanismo basáltico primitivo com Marte [Texto Demonstrativo].'
      }
    }),

    mars_reference: Object.freeze({
      id: 'mars_reference',
      targetBadge: 'CORPO CELESTE DE COMPARAÇÃO // MARTE',
      selectedTarget: {
        name: 'Marte — Parâmetros de Referência',
        classification: 'Planeta Terrestre Rochoso (Placeholder)',
        biomeContext: 'Crioesfera Árida com Atmosfera Rarefeita de CO₂ [Demonstrativo]'
      },
      coordinates: {
        latitude: '18° 22\' 48" N',
        longitude: '77° 34\' 48" E',
        elevation: '-2.500 m (Jezero Crater Ref. - Placeholder)',
        datum: 'Areocêntrico (MOLA Sphere)'
      },
      environmentalIndicators: {
        solarIrradiance: '590 W/m² (Topo da Atmosfera) [Placeholder]',
        atmosphericPressure: '0,636 kPa (~6,36 mbar) [Placeholder]',
        uvIndex: 'Elevado (UVC/UVB atinge a superfície) [Demonstrativo]',
        relativeHumidity: 'Variável (Saturação noturna de vapor traço) [Placeholder]'
      },
      topography: {
        reliefType: 'Deltas fósseis, cânions tectônicos e escudos vulcânicos [Placeholder]',
        averageSlope: '3,8° a 21,0° [Dados Fictícios]',
        roughnessIndex: 'Moderado a Alto (Campos de matacões) [Placeholder]'
      },
      geology: {
        lithology: 'Basaltos ricos em ferro, argilominerais (filossilicatos) e carbonatos [Placeholder]',
        soilComposition: 'Regolito oxidado (hematita/magnetita), sulfatos e percloratos [Demonstrativo]',
        stratigraphy: 'Sequências fluvio-lacustres Noachianas/Hesperianas [Placeholder]'
      },
      temperature: {
        meanAnnual: '-63 °C [Demonstrativo]',
        diurnalRange: '-110 °C a +20 °C [Placeholder]',
        surfaceThermalInertia: 'Moderada-Baixa [Dados Fictícios]'
      },
      waterAndIce: {
        surfaceWater: 'Gelo polar (H₂O e CO₂); salmouras transitórias sob investigação [Placeholder]',
        subsurfaceIce: 'Lençóis de gelo subsuperficial em médias e altas latitudes [Demonstrativo]',
        hydrologicalRegime: 'Paleohidrologia ativa no passado; criosfera atual [Placeholder]'
      },
      planetaryComparison: {
        lunarAnalogScore: 'N/A [Corpo Marciano]',
        lunarRelevance:
          'Regiões vulcânicas basálticas apresentam paralelos geotécnicos com mares lunares [Texto Demonstrativo].',
        martianAnalogScore: '100% [Referência Base]',
        martianRelevance:
          'Parâmetros de referência para comparação futura com desertos hiperáridos e polares terrestres (Atacama, Vales Secos de McMurdo, Devon Island) [Placeholder].'
      }
    })
  })
});
