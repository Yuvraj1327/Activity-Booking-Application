import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import '../../core/config/app_config.dart';
import '../../core/constants/tokens.dart';
import '../../core/utils/format.dart';
import '../../shared/models/venue.dart';
import '../../shared/widgets/common_widgets.dart';
import '../categories/categories_provider.dart';
import '../home/home_providers.dart';
import '../location/location_controller.dart';
import '../location/location_sheet.dart';
import 'filter_sheets.dart';
import 'venue_list_controller.dart';

/// Search + filter + sort over published venues, with infinite scroll.
/// Used as the Explore tab and, with [fixedCategory], as a sport's results page.
class VenueListScreen extends ConsumerStatefulWidget {
  const VenueListScreen({super.key, this.fixedCategory, this.title = 'Explore'});

  final String? fixedCategory;
  final String title;

  @override
  ConsumerState<VenueListScreen> createState() => _VenueListScreenState();
}

class _VenueListScreenState extends ConsumerState<VenueListScreen> {
  final _search = TextEditingController();
  final _searchFocus = FocusNode();
  final _scroll = ScrollController();
  Timer? _debounce;

  String _text = '';
  String? _category;
  int? _minPrice;
  int? _maxPrice;
  VenueSort _sort = VenueSort.popular;
  bool _nearMe = false;

  @override
  void initState() {
    super.initState();
    _category = widget.fixedCategory;
    _scroll.addListener(_onScroll);
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _search.dispose();
    _searchFocus.dispose();
    _scroll.dispose();
    super.dispose();
  }

  VenueQuery _query(LocationState location) {
    final point = location.point;
    final nearMe = _nearMe && point != null;
    return VenueQuery(
      text: _text,
      category: _category,
      // "Near me" is about distance, so it replaces the city filter.
      cityId: nearMe ? null : location.city?.id,
      minPricePaise: _minPrice,
      maxPricePaise: _maxPrice,
      // Send the position whenever we have it so cards can show distance.
      lat: point == null ? null : (point.lat * 100).roundToDouble() / 100,
      lng: point == null ? null : (point.lng * 100).roundToDouble() / 100,
      radiusKm: nearMe ? AppConfig.nearbyRadiusKm : null,
      sort: nearMe && _sort == VenueSort.popular ? VenueSort.distance : _sort,
      pageSize: AppConfig.pageSize,
    );
  }

  void _onScroll() {
    if (!_scroll.hasClients) return;
    if (_scroll.position.pixels >= _scroll.position.maxScrollExtent - 400) {
      final query = _query(ref.read(locationControllerProvider));
      ref.read(venueListControllerProvider(query).notifier).loadMore();
    }
  }

  void _onSearchChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(AppConfig.searchDebounce, () {
      if (mounted) setState(() => _text = value.trim());
    });
    setState(() {}); // refresh the clear button
  }

  void _clearAll() {
    _debounce?.cancel();
    _search.clear();
    setState(() {
      _text = '';
      _category = widget.fixedCategory;
      _minPrice = null;
      _maxPrice = null;
      _sort = VenueSort.popular;
      _nearMe = false;
    });
  }

  Future<void> _toggleNearMe(bool selected) async {
    if (!selected) {
      setState(() => _nearMe = false);
      return;
    }
    var hasPoint = ref.read(locationControllerProvider).hasPoint;
    if (!hasPoint) hasPoint = await enableLocation(context, ref);
    if (mounted && hasPoint) setState(() => _nearMe = true);
  }

  Future<void> _pickPrice() async {
    final result = await showPriceSheet(context, initial: PriceRange(min: _minPrice, max: _maxPrice));
    if (result != null && mounted) {
      setState(() {
        _minPrice = result.min;
        _maxPrice = result.max;
      });
    }
  }

  Future<void> _pickMore() async {
    final categories = ref.read(categoriesProvider).valueOrNull ?? const [];
    final result = await showMoreFiltersSheet(
      context,
      categories: categories,
      lockCategory: widget.fixedCategory != null,
      initial: MoreFilters(category: _category, sort: _sort),
      distanceAvailable: ref.read(locationControllerProvider).hasPoint,
    );
    if (result != null && mounted) {
      setState(() {
        _category = widget.fixedCategory ?? result.category;
        _sort = result.sort;
      });
    }
  }

  String get _priceLabel {
    if (_minPrice == null && _maxPrice == null) return 'Price';
    if (_minPrice == null) return 'Up to ${formatMoney(_maxPrice!)}';
    if (_maxPrice == null) return 'From ${formatMoney(_minPrice!)}';
    return '${formatMoney(_minPrice!)} – ${formatMoney(_maxPrice!)}';
  }

  bool get _hasActiveFilters =>
      _text.isNotEmpty ||
      _nearMe ||
      _minPrice != null ||
      _maxPrice != null ||
      _sort != VenueSort.popular ||
      _category != widget.fixedCategory;

  @override
  Widget build(BuildContext context) {
    // Home's search bar asks this tab to focus the field.
    ref.listen<int>(exploreFocusRequestProvider, (prev, next) {
      if (widget.fixedCategory == null && prev != next) _searchFocus.requestFocus();
    });

    final theme = Theme.of(context);
    final location = ref.watch(locationControllerProvider);
    final query = _query(location);
    final state = ref.watch(venueListControllerProvider(query));
    final controller = ref.read(venueListControllerProvider(query).notifier);
    final canPop = Navigator.of(context).canPop();
    final categories = ref.watch(categoriesProvider).valueOrNull ?? const [];
    final moreActive = (_category != widget.fixedCategory && widget.fixedCategory == null) || _sort != VenueSort.popular;

    return Scaffold(
      appBar: AppBar(
        automaticallyImplyLeading: false,
        leading: canPop ? IconButton(onPressed: () => context.pop(), icon: const Icon(Icons.arrow_back_rounded)) : null,
        title: Text(widget.title, style: theme.textTheme.titleLarge),
        actions: [
          TextButton.icon(
            onPressed: () => showCitySheet(context),
            icon: const Icon(Icons.place_outlined, size: 18),
            label: Text(location.city?.name ?? 'City'),
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(Gap.page, 4, Gap.page, 8),
            child: TextField(
              controller: _search,
              focusNode: _searchFocus,
              textInputAction: TextInputAction.search,
              onChanged: _onSearchChanged,
              onSubmitted: (v) {
                _debounce?.cancel();
                setState(() => _text = v.trim());
              },
              decoration: InputDecoration(
                hintText: 'Search venues, sports or areas',
                prefixIcon: const Icon(Icons.search_rounded),
                suffixIcon: _search.text.isEmpty
                    ? null
                    : IconButton(
                        tooltip: 'Clear search',
                        icon: const Icon(Icons.close_rounded),
                        onPressed: () {
                          _debounce?.cancel();
                          _search.clear();
                          setState(() => _text = '');
                        },
                      ),
                filled: true,
                fillColor: ZuruvColors.primaryTint,
                contentPadding: const EdgeInsets.symmetric(vertical: 14),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(Radii.button), borderSide: BorderSide.none),
                enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(Radii.button), borderSide: BorderSide.none),
              ),
            ),
          ),
          SizedBox(
            height: 44,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: Gap.page),
              children: [
                FilterChip(
                  avatar: const Icon(Icons.near_me_rounded, size: 16),
                  label: const Text('Near Me'),
                  selected: _nearMe,
                  onSelected: location.locating ? null : _toggleNearMe,
                ),
                const SizedBox(width: 8),
                // Needs availability data, which arrives with booking. Disabled on purpose.
                const Tooltip(
                  message: 'Available with booking, coming soon',
                  child: FilterChip(label: Text('Today'), selected: false, onSelected: null),
                ),
                const SizedBox(width: 8),
                FilterChip(
                  label: Text(_priceLabel),
                  selected: _minPrice != null || _maxPrice != null,
                  onSelected: (_) => _pickPrice(),
                ),
                const SizedBox(width: 8),
                FilterChip(
                  avatar: const Icon(Icons.tune_rounded, size: 16),
                  label: const Text('More'),
                  selected: moreActive,
                  onSelected: (_) => _pickMore(),
                ),
              ],
            ),
          ),
          if (widget.fixedCategory == null && _category != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(Gap.page, 8, Gap.page, 0),
              child: Align(
                alignment: Alignment.centerLeft,
                child: InputChip(
                  label: Text(categories.where((c) => c.slug == _category).map((c) => c.name).firstOrNull ?? _category!),
                  onDeleted: () => setState(() => _category = null),
                ),
              ),
            ),
          const SizedBox(height: 8),
          Expanded(
            child: _Results(
              state: state,
              scroll: _scroll,
              onRefresh: controller.refresh,
              onRetryMore: controller.loadMore,
              hasFilters: _hasActiveFilters,
              onClear: _clearAll,
              cityName: location.city?.name,
            ),
          ),
        ],
      ),
    );
  }
}

class _Results extends StatelessWidget {
  const _Results({
    required this.state,
    required this.scroll,
    required this.onRefresh,
    required this.onRetryMore,
    required this.hasFilters,
    required this.onClear,
    required this.cityName,
  });

  final VenueListState state;
  final ScrollController scroll;
  final Future<void> Function() onRefresh;
  final VoidCallback onRetryMore;
  final bool hasFilters;
  final VoidCallback onClear;
  final String? cityName;

  @override
  Widget build(BuildContext context) {
    if (state.loading && state.items.isEmpty) {
      return ListView.separated(
        padding: const EdgeInsets.all(Gap.page),
        itemCount: 3,
        separatorBuilder: (_, __) => const SizedBox(height: 20),
        itemBuilder: (_, __) => const VenueCardSkeleton(),
      );
    }
    if (state.error != null) {
      return ErrorView.fromError(state.error!, onRetry: onRefresh);
    }
    if (state.items.isEmpty) {
      return EmptyState(
        icon: Icons.search_off_rounded,
        title: 'No venues found',
        message: hasFilters
            ? 'Try a different search or clear your filters.'
            : (cityName == null ? 'No venues are listed yet.' : 'No venues in $cityName yet. Try another city.'),
        action: hasFilters ? OutlinedButton(onPressed: onClear, child: const Text('Clear filters')) : null,
      );
    }
    return RefreshIndicator(
      onRefresh: onRefresh,
      child: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: ListView.separated(
            controller: scroll,
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(Gap.page, 4, Gap.page, 24),
            itemCount: state.items.length + 1,
            separatorBuilder: (_, __) => const SizedBox(height: 16),
            itemBuilder: (context, i) {
              if (i == state.items.length) {
                return ListFooter(loading: state.loadingMore, error: state.loadMoreError != null, onRetry: onRetryMore);
              }
              final venue = state.items[i];
              return VenueCard(venue: venue, onTap: () => context.push('/venues/${venue.id}'));
            },
          ),
        ),
      ),
    );
  }
}
