import 'package:flutter/material.dart';

import 'package:zuruv/core/config/app_config.dart';
import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/customer/core/utils/format.dart';
import 'package:zuruv/customer/shared/models/catalog.dart';
import 'package:zuruv/customer/shared/models/venue.dart';

/// Price per hour in paise; null on either side means unbounded.
class PriceRange {
  const PriceRange({this.min, this.max});
  final int? min;
  final int? max;
}

/// Price filter: a rupee slider whose far-right stop means "no upper limit".
Future<PriceRange?> showPriceSheet(BuildContext context, {required PriceRange initial}) {
  return showModalBottomSheet<PriceRange>(
    context: context,
    isScrollControlled: true,
    builder: (_) => _PriceSheet(initial: initial),
  );
}

class _PriceSheet extends StatefulWidget {
  const _PriceSheet({required this.initial});
  final PriceRange initial;

  @override
  State<_PriceSheet> createState() => _PriceSheetState();
}

class _PriceSheetState extends State<_PriceSheet> {
  static const double _max = AppConfig.priceSliderMaxRupees * 1.0;
  late RangeValues _values = RangeValues(
    ((widget.initial.min ?? 0) / 100).clamp(0, _max).toDouble(),
    widget.initial.max == null ? _max : (widget.initial.max! / 100).clamp(0, _max).toDouble(),
  );

  String _label(double rupees, {required bool isMax}) {
    if (isMax && rupees >= _max) return '₹${AppConfig.priceSliderMaxRupees}+';
    return formatMoney(rupees.round() * 100);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(Gap.page, 0, Gap.page, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Price per hour', style: theme.textTheme.titleLarge),
            const SizedBox(height: 4),
            Text('${_label(_values.start, isMax: false)} – ${_label(_values.end, isMax: true)}',
                style: theme.textTheme.titleMedium?.copyWith(color: theme.colorScheme.primary)),
            RangeSlider(
              values: _values,
              min: 0,
              max: _max,
              divisions: AppConfig.priceSliderMaxRupees ~/ AppConfig.priceSliderStepRupees,
              labels: RangeLabels(_label(_values.start, isMax: false), _label(_values.end, isMax: true)),
              onChanged: (v) => setState(() => _values = v),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => Navigator.of(context).pop(const PriceRange()),
                    child: const Text('Clear'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton(
                    onPressed: () => Navigator.of(context).pop(
                      PriceRange(
                        min: _values.start <= 0 ? null : _values.start.round() * 100,
                        max: _values.end >= _max ? null : _values.end.round() * 100,
                      ),
                    ),
                    child: const Text('Apply'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class MoreFilters {
  const MoreFilters({this.category, required this.sort});
  final String? category;
  final VenueSort sort;
}

/// "More" filters: sport (unless the screen is already about one sport) and sort order.
Future<MoreFilters?> showMoreFiltersSheet(
  BuildContext context, {
  required List<VenueCategory> categories,
  required bool lockCategory,
  required MoreFilters initial,
  required bool distanceAvailable,
}) {
  return showModalBottomSheet<MoreFilters>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    builder: (_) => _MoreSheet(
      categories: categories,
      lockCategory: lockCategory,
      initial: initial,
      distanceAvailable: distanceAvailable,
    ),
  );
}

class _MoreSheet extends StatefulWidget {
  const _MoreSheet({
    required this.categories,
    required this.lockCategory,
    required this.initial,
    required this.distanceAvailable,
  });

  final List<VenueCategory> categories;
  final bool lockCategory;
  final MoreFilters initial;
  final bool distanceAvailable;

  @override
  State<_MoreSheet> createState() => _MoreSheetState();
}

class _MoreSheetState extends State<_MoreSheet> {
  late String? _category = widget.initial.category;
  late VenueSort _sort = widget.initial.sort;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(Gap.page, 0, Gap.page, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Filters', style: theme.textTheme.titleLarge),
          if (!widget.lockCategory && widget.categories.isNotEmpty) ...[
            const SizedBox(height: 16),
            Text('Sport', style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                ChoiceChip(label: const Text('All'), selected: _category == null, onSelected: (_) => setState(() => _category = null)),
                for (final c in widget.categories)
                  ChoiceChip(
                    label: Text(c.name),
                    selected: _category == c.slug,
                    onSelected: (_) => setState(() => _category = c.slug),
                  ),
              ],
            ),
          ],
          const SizedBox(height: 20),
          Text('Sort by', style: theme.textTheme.titleMedium),
          const SizedBox(height: 4),
          for (final option in VenueSort.values)
            ListTile(
              contentPadding: EdgeInsets.zero,
              enabled: option != VenueSort.distance || widget.distanceAvailable,
              title: Text(option.label),
              subtitle: option == VenueSort.distance && !widget.distanceAvailable
                  ? const Text('Turn on location to sort by distance')
                  : null,
              trailing: _sort == option ? Icon(Icons.check_circle_rounded, color: theme.colorScheme.primary) : null,
              onTap: () => setState(() => _sort = option),
            ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: () => Navigator.of(context).pop(
                    MoreFilters(category: widget.lockCategory ? widget.initial.category : null, sort: VenueSort.popular),
                  ),
                  child: const Text('Reset'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton(
                  onPressed: () => Navigator.of(context).pop(MoreFilters(category: _category, sort: _sort)),
                  child: const Text('Apply'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
