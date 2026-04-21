# Activity Detail Payload Audit

DB: `temperance/data/private/users/admin.db`
Rows: `1181`
Total details_json MB: `570.7`

## Largest Rows

- `20705627024`: `1872.5 KB`
- `16081289056`: `1869.5 KB`
- `18014388416`: `1868.5 KB`
- `20625411547`: `1861.5 KB`
- `17613170971`: `1853.4 KB`
- `20398235455`: `1844.3 KB`
- `17314890988`: `1843.8 KB`
- `17783675510`: `1838.1 KB`
- `20362139235`: `1830.3 KB`
- `20972811082`: `1816.2 KB`

## Detail Key Counts

- `activityId`: `1181`
- `measurementCount`: `1181`
- `metricsCount`: `1181`
- `totalMetricsCount`: `1181`
- `metricDescriptors`: `1181`
- `activityDetailMetrics`: `1181`
- `geoPolylineDTO`: `1181`
- `heartRateDTOs`: `1181`
- `pendingData`: `1181`
- `detailsAvailable`: `1181`

## Heavy Key Estimated Bytes

- `activityDetailMetrics`: `321.9 MB`
- `geoPolylineDTO`: `190.4 MB`
- `metricDescriptors`: `2.6 MB`
- `heartRateDTOs`: `0.0 MB`

## Recommendation

Keep compact metadata, weather scalar fields, and HR zone rows. Drop full metric arrays, metric descriptors, heart-rate DTO arrays, and polylines from default DB storage.
