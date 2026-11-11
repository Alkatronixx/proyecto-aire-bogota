## Resultado

Ejecuté [diagnostico_alineacion.py](</D:/ciencia de datos/proyecto-aire-bogota/src/modelo/diagnostico_alineacion.py>) con corte de entrenamiento hasta **2025-10-23**, prueba del **2025-10-24 al 2026-10-23**, y `random_state=42`. No guardé modelos ni modifiqué archivos existentes de datos o decisiones. Las tablas nuevas están en `data/processed/app/` con el prefijo solicitado.

La anomalía es PM2.5 menos la media de entrenamiento por estación y mes. Como en `entrenar_v2.py`, pares estación-mes con menos de 10 observaciones usan la media de la estación; si no existe la estación, se usa la media global. En las tablas siguientes, **n cuenta observaciones estación-día válidas**, no fechas únicas. La climatología se calculó usando solo fechas de entrenamiento.

### Correlaciones y anomalía media según lluvia

Spearman se reporta como `rho (n)`. Las tres columnas de lluvia muestran la anomalía media con lluvia, sin lluvia y la diferencia **con − sin**; cada media incluye su n.

| Grupo IDEAM | k | Precip. | Llueve ≥1 mm | Tmax anomalía | Tmin anomalía | Amplitud | Anomalía con lluvia (n) | Sin lluvia (n) | Con − sin (n) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Global | -2 | -0,017 (15573) | -0,031 (15573) | 0,074 (16277) | 0,042 (16329) | 0,012 (16156) | -1,50 (7385) | -0,91 (8188) | -0,59 (15573) |
| Global | -1 | -0,024 (15577) | -0,031 (15577) | 0,102 (16297) | 0,042 (16347) | 0,015 (16176) | -1,48 (7372) | -0,86 (8205) | -0,62 (15577) |
| Global | 0 | 0,062 (15578) | 0,036 (15578) | 0,088 (16317) | 0,039 (16363) | -0,009 (16196) | -1,05 (7340) | -1,30 (8238) | 0,25 (15578) |
| Global | +1 | 0,060 (15555) | 0,041 (15555) | 0,042 (16300) | 0,088 (16342) | -0,064 (16176) | -1,09 (7328) | -1,36 (8227) | 0,27 (15555) |
| Global | +2 | 0,041 (15531) | 0,030 (15531) | 0,008 (16293) | 0,093 (16322) | -0,062 (16166) | -1,16 (7301) | -1,32 (8230) | 0,16 (15531) |
| Nueva Generación | -2 | -0,057 (3377) | -0,022 (3377) | 0,095 (7563) | 0,049 (7615) | 0,018 (7461) | -1,46 (1129) | -0,94 (2248) | -0,51 (3377) |
| Nueva Generación | -1 | -0,107 (3379) | -0,052 (3379) | 0,126 (7573) | 0,030 (7623) | 0,046 (7471) | -1,75 (1126) | -0,80 (2253) | -0,95 (3379) |
| Nueva Generación | 0 | 0,004 (3380) | 0,031 (3380) | 0,143 (7583) | -0,006 (7629) | 0,082 (7481) | -0,99 (1108) | -1,15 (2272) | 0,16 (3380) |
| Nueva Generación | +1 | 0,021 (3378) | 0,038 (3378) | 0,096 (7574) | 0,113 (7617) | -0,034 (7469) | -0,92 (1114) | -1,20 (2264) | 0,29 (3378) |
| Nueva Generación | +2 | 0,022 (3372) | 0,045 (3372) | 0,050 (7577) | 0,162 (7606) | -0,097 (7468) | -0,79 (1106) | -1,24 (2266) | 0,45 (3372) |
| Jardín Botánico | -2 | 0,012 (8771) | -0,017 (8771) | — | — | — | -1,49 (4464) | -1,08 (4307) | -0,41 (8771) |
| Jardín Botánico | -1 | 0,033 (8769) | 0,008 (8769) | — | — | — | -1,33 (4448) | -1,13 (4321) | -0,20 (8769) |
| Jardín Botánico | 0 | 0,088 (8765) | 0,051 (8765) | — | — | — | -1,08 (4438) | -1,50 (4327) | 0,42 (8765) |
| Jardín Botánico | +1 | 0,063 (8748) | 0,039 (8748) | — | — | — | -1,30 (4422) | -1,48 (4326) | 0,18 (8748) |
| Jardín Botánico | +2 | 0,046 (8734) | 0,023 (8734) | — | — | — | -1,42 (4394) | -1,41 (4340) | -0,01 (8734) |
| San Cayetano | -2 | -0,051 (3425) | -0,066 (3425) | 0,061 (8714) | 0,039 (8714) | 0,022 (8695) | -1,53 (1792) | -0,41 (1633) | -1,12 (3425) |
| San Cayetano | -1 | -0,095 (3429) | -0,112 (3429) | 0,082 (8724) | 0,065 (8724) | 0,018 (8705) | -1,68 (1798) | -0,22 (1631) | -1,46 (3429) |
| San Cayetano | 0 | 0,050 (3433) | 0,011 (3433) | 0,032 (8734) | 0,109 (8734) | -0,103 (8715) | -0,99 (1794) | -0,96 (1639) | -0,03 (3433) |
| San Cayetano | +1 | 0,094 (3429) | 0,060 (3429) | -0,020 (8726) | 0,079 (8725) | -0,126 (8707) | -0,69 (1792) | -1,27 (1637) | 0,58 (3429) |
| San Cayetano | +2 | 0,056 (3425) | 0,048 (3425) | -0,036 (8716) | 0,022 (8716) | -0,081 (8698) | -0,76 (1801) | -1,20 (1624) | 0,44 (3425) |

Jardín Botánico no está asignado como fuente de temperatura en estas estaciones de aire, por eso sus métricas de temperatura no aplican. Las asociaciones más fuertes cambian de desfase según variable y grupo; sus magnitudes son pequeñas. Globalmente, la asociación más fuerte con precipitación es `precip_mm` en **k=0, rho=0,062**; para `llueve`, **k=+1, rho=0,041**. Para temperatura, los máximos absolutos globales son `tmax_anom` en **k=-1, rho=0,102**, `tmin_anom` en **k=+2, rho=0,093** y amplitud en **k=+1, rho=-0,064**.

### Ridge de anomalías y ablación

Se usó Ridge con `alpha=100`, imputación mediana y estandarización, entrenado sobre las **8.905 filas completas** del filtro de `entrenar_v2.py`. Ambas variantes se evaluaron sobre las mismas **5.258 observaciones completas de prueba**. La climatología tuvo MAE **5,461** en esas filas.

| Variante | Filas prueba | MAE | RMSE | R² | MAE climatología |
|---|---:|---:|---:|---:|---:|
| IDEAM k=0 | 5.258 | 5,441 | 6,891 | 0,269 | 5,461 |
| IDEAM k=+1 | 5.258 | 5,397 | 6,880 | 0,272 | 5,461 |

La variante k=+1 mejora el MAE de k=0 en **0,044 µg/m³**. La ablación, reentrenando cada variante k=+1 sin el grupo indicado, dio:

| Grupo excluido | MAE sin grupo | MAE modelo completo | MAE climatología |
|---|---:|---:|---:|
| Lluvia | 5,349 | 5,397 | 5,461 |
| Temperatura | 5,423 | 5,397 | 5,461 |
| Viento | 5,467 | 5,397 | 5,461 |
| Calendario | 5,470 | 5,397 | 5,461 |

### Fechas y categorías en metadatos

En los archivos crudos diarios revisados, las **7.705 fechas de precipitación**, **2.910 de Tmax** y **3.119 de Tmin** incluyen hora `00:00`; ninguna tiene hora distinta de medianoche. En los archivos de humedad también hay componente horaria: 21.412 registros inspeccionados, 20.522 con hora distinta de cero.

Los metadatos clasifican las tres estaciones así; estas categorías son las que aparecen en el catálogo, no etiquetas “convencional” o “automática”:

| Estación | Categoría de metadatos |
|---|---|
| Nueva Generación | Climatológica Principal |
| Jardín Botánico | Climatológica Principal |
| San Cayetano | Climatológica Ordinaria |

Archivos con resultados de precisión completa: [correlaciones](</D:/ciencia de datos/proyecto-aire-bogota/data/processed/app/diagnostico_alineacion_correlaciones.csv>), [métricas Ridge](</D:/ciencia de datos/proyecto-aire-bogota/data/processed/app/diagnostico_alineacion_metricas_ridge.csv>), [ablación](</D:/ciencia de datos/proyecto-aire-bogota/data/processed/app/diagnostico_alineacion_ablacion_k1.csv>), [revisión de fechas crudas](</D:/ciencia de datos/proyecto-aire-bogota/data/processed/app/diagnostico_alineacion_fechas_crudas.csv>) y [categorías](</D:/ciencia de datos/proyecto-aire-bogota/data/processed/app/diagnostico_alineacion_categorias_ideam.csv>).

## Cierre: evidencia y decisión

1. Las fechas de precipitación y temperatura traen `00:00`, pero eso por sí solo no confirma el intervalo meteorológico de 7 a. m. a 7 a. m.
2. Las correlaciones más fuertes aparecen en desfases distintos; el patrón no señala un desplazamiento uniforme de un día.
3. k=+1 mejora el MAE frente a k=0 en 0,044 µg/m³ sobre las mismas 5.258 filas; el cambio es pequeño.
4. Los datos ofrecen evidencia débil y mixta para el desfase; corresponde decidir si se mantiene k=0 o se adopta k=+1 como hipótesis de modelado.
5. Antes de cambiar la alineación operativa, conviene confirmar con documentación del IDEAM qué periodo representa la fecha diaria de esos archivos.
