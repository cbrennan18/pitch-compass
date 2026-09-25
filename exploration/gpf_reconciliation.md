# GPF reconciliation
Source: gaapitchfinder_data.csv @ commit `256eb08482b2c385614415db18841f8a43e1f61b`, CC BY 4.0.
Club and pitch location data from GAA Pitch Finder by Ryan McGuinness: https://gaapitchfinder.com

41 GPF rows match the `<County> GAA` pattern (island scope, `File=='Ireland'`).

## Per-county match table
| County | GPF ground(s) | CSV county_main | Distance | Notes |
|---|---|---|---|---|
| Antrim | Casement Park | Casement Park | 9m | OK |
| Armagh | Athletic Grounds | Athletic Grounds | 25m | OK |
| Carlow | Dr. Cullen Park | Dr Cullen Park | 42m | OK |
| Cavan | Breffni Park | Breffni Park | 24m | OK |
| Clare | Cusack Park (Ennis) | Cusack Park | 7m | OK |
| Cork | Páirc Uí Chaoimh | Pairc Ui Chaoimh | 5m | OK |
| Cork | Páirc Uí Rinn * | Pairc Ui Rinn | 139m | re-matched via GPF coord: matched_inside_boundary, bearing 89.3 -> 89.3 (unchanged) |
| Derry | Páirc na gCeilteach | Celtic Park | 147m | re-matched via GPF coord: matched_inside_boundary, bearing 26.9 -> 26.9 (unchanged) |
| Donegal | MacCumhail Park | MacCumhaill Park | 152m | >50m but satellite-verified -- not re-matched |
| Donegal | O'Donnell Park * | O'Donnell Park | 126m | re-matched via GPF coord: still needs_manual (n_candidates=2) |
| Donegal | Fr Tierney Park * | Fr Tierney Park | 160m | >50m but satellite-verified -- not re-matched |
| Down | Páirc Esler | Pairc Esler | 194m | re-matched via GPF coord: still needs_manual (n_candidates=0) |
| Down | McKenna Park * | McKenna Park | 147m | re-matched via GPF coord: matched_150m_radius, bearing 153.2 -> 153.2 (unchanged) |
| Dublin | Parnell Park | Parnell Park | 149m | re-matched via GPF coord: matched_inside_boundary, bearing 112.5 -> 112.5 (unchanged) |
| Dublin | Croke Park * | Croke Park | 60m | re-matched via GPF coord: matched_inside_boundary, bearing 19.3 -> 19.3 (unchanged) |
| Fermanagh | Brewster Park | Brewster Park | 24m | OK |
| Galway | Pearse Stadium | Pearse Stadium | 125m | re-matched via GPF coord: matched_inside_boundary, bearing 72.7 -> 72.7 (unchanged) |
| Galway | St Jarlath's Park * | St Jarlath's Park | 135m | re-matched via GPF coord: matched_inside_boundary, bearing 0.4 -> 0.4 (unchanged) |
| Kerry | Fitzgerald Stadium | Fitzgerald Stadium | 167m | re-matched via GPF coord: still needs_manual (n_candidates=0) |
| Kerry | Austin Stack Park * | Austin Stack Park | 140m | re-matched via GPF coord: matched_inside_boundary, bearing 101.7 -> 101.7 (unchanged) |
| Kildare | St Conleth's Park | St Conleth's Park | 139m | re-matched via GPF coord: matched_inside_boundary, bearing 138.6 -> 138.6 (unchanged) |
| Kilkenny | Nowlan Park | Nowlan Park | 149m | re-matched via GPF coord: matched_inside_boundary, bearing 35.8 -> 35.8 (unchanged) |
| Laois | O'Moore Park | O'Moore Park | 131m | re-matched via GPF coord: matched_inside_boundary, bearing 166.7 -> 166.7 (unchanged) |
| Leitrim | Páirc Seán Mac Diarmada | Pairc Sean Mac Diarmada | 145m | re-matched via GPF coord: matched_inside_boundary, bearing 36.5 -> 36.5 (unchanged) |
| Limerick | Gaelic Grounds | Gaelic Grounds | 135m | re-matched via GPF coord: matched_inside_boundary, bearing 83.1 -> 83.1 (unchanged) |
| Longford | Pearse Park | Pearse Park | 152m | re-matched via GPF coord: still needs_manual (n_candidates=0) |
| Louth | Gaelic Grounds | Gaelic Grounds | 10m | OK |
| Mayo | MacHale Park | MacHale Park | 133m | re-matched via GPF coord: matched_inside_boundary, bearing 13.3 -> 13.3 (unchanged) |
| Meath | Páirc Tailteann | Pairc Tailteann | 132m | re-matched via GPF coord: matched_inside_boundary, bearing 69.3 -> 69.3 (unchanged) |
| Monaghan | St Tiernach's Park | St Tiernach's Park | 168m | re-matched via GPF coord: matched_inside_boundary, bearing 73.6 -> 73.6 (unchanged) |
| Offaly | O'Connor Park | O'Connor Park | 134m | re-matched via GPF coord: matched_inside_boundary, bearing 98.0 -> 98.0 (unchanged) |
| Offaly | St Brendan's Park * | St Brendan's Park | 150m | re-matched via GPF coord: matched_inside_boundary, bearing 4.4 -> 4.4 (unchanged) |
| Roscommon | Dr. Hyde Park | Dr Hyde Park | 133m | re-matched via GPF coord: matched_150m_radius, bearing 114.8 -> 114.8 (unchanged) |
| Sligo | Markievicz Park | Markievicz Park | 141m | re-matched via GPF coord: matched_150m_radius, bearing 157.8 -> 157.8 (unchanged) |
| Tipperary | Semple Stadium | Semple Stadium | 104m | re-matched via GPF coord: matched_inside_boundary, bearing 91.9 -> 91.9 (unchanged) |
| Tyrone | Healy Park | Healy Park | 127m | >50m but satellite-verified -- not re-matched |
| Waterford | Walsh Park | Walsh Park | 131m | re-matched via GPF coord: matched_inside_boundary, bearing 78.8 -> 78.8 (unchanged) |
| Waterford | Fraher Field * | Fraher Field | 136m | re-matched via GPF coord: matched_inside_boundary, bearing 87.6 -> 87.6 (unchanged) |
| Westmeath | Cusack Park (Mullingar) | Cusack Park | 130m | re-matched via GPF coord: matched_inside_boundary, bearing 71.0 -> 71.0 (unchanged) |
| Wexford | Wexford Park | Wexford Park | 129m | re-matched via GPF coord: matched_150m_radius, bearing 77.3 -> 77.3 (unchanged) |
| Wicklow | Aughrim County Ground | Aughrim County Ground | 134m | >50m but satellite-verified -- not re-matched |

`*` = this GPF row's nearest CSV match is not that county's `county_main`.

## Counties with more than one `<County> GAA` row in GPF
- **Cork**: Páirc Uí Chaoimh, Páirc Uí Rinn
- **Donegal**: MacCumhail Park, O'Donnell Park, Fr Tierney Park
- **Down**: Páirc Esler, McKenna Park
- **Dublin**: Parnell Park, Croke Park
- **Galway**: Pearse Stadium, St Jarlath's Park
- **Kerry**: Fitzgerald Stadium, Austin Stack Park
- **Offaly**: O'Connor Park, St Brendan's Park
- **Waterford**: Walsh Park, Fraher Field

## Known mismatches worth flagging
- **Dublin**: GPF ties `Dublin GAA` to both Parnell Park and Croke Park. Per your instruction, Croke Park stays `role=national`, Parnell Park is `county_main` -- not double-counted as two Dublin county grounds.
- **Donegal**: GPF lists three `Donegal GAA` grounds (MacCumhaill Park, O'Donnell Park, Fr Tierney Park); county_grounds.csv now carries all three (main + two seconds), matching GPF.
- **Antrim**: GPF ties `Antrim GAA` to Casement Park, matching your principal-venue rule (Casement = county_main despite closure since 2013).
- **Louth**: GPF still lists the old Drogheda Gaelic Grounds as `Louth GAA`'s ground -- no sign of the Dundalk move in GPF's data either, consistent with your "home until 2020, new stadium not yet open" framing.
