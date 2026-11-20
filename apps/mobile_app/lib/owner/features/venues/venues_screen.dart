import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';

import 'package:zuruv/core/config/app_config.dart';
import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/owner/core/utils/format.dart';
import 'package:zuruv/owner/shared/models/models.dart';
import 'package:zuruv/owner/shared/repositories/owner_repository.dart';
import 'package:zuruv/owner/shared/widgets/common_widgets.dart';
import 'package:zuruv/owner/shared/widgets/z_network_image.dart';
import 'package:zuruv/owner/features/dashboard/dashboard_screen.dart';

class VenueListState {
  const VenueListState({
    this.items = const [],
    this.loading = false,
    this.loadingMore = false,
    this.error,
    this.hasMore = false,
    this.query = '',
    this.status,
  });
  final List<OwnerVenueCard> items;
  final bool loading;
  final bool loadingMore;
  final String? error;
  final bool hasMore;
  final String query;
  final String? status; // null = all

  bool get filtered => query.isNotEmpty || status != null;

  VenueListState copyWith({
    List<OwnerVenueCard>? items,
    bool? loading,
    bool? loadingMore,
    String? error,
    bool clearError = false,
    bool? hasMore,
    String? query,
    String? status,
    bool clearStatus = false,
  }) =>
      VenueListState(
        items: items ?? this.items,
        loading: loading ?? this.loading,
        loadingMore: loadingMore ?? this.loadingMore,
        error: clearError ? null : (error ?? this.error),
        hasMore: hasMore ?? this.hasMore,
        query: query ?? this.query,
        status: clearStatus ? null : (status ?? this.status),
      );
}

/// The owner's own venues (`GET /owners/venues`): search, status filter and paging.
class VenueListController extends Notifier<VenueListState> {
  int _generation = 0; // ignores answers to requests that are no longer current

  @override
  VenueListState build() {
    Future.microtask(refresh);
    return const VenueListState(loading: true);
  }

  Future<void> refresh() async {
    final gen = ++_generation;
    state = state.copyWith(loading: true, clearError: true);
    try {
      final page = await ref.read(ownerRepositoryProvider).venues(
            query: state.query,
            status: state.status,
            limit: AppConfig.pageSize,
          );
      if (gen != _generation) return;
      state = state.copyWith(items: page.items, hasMore: page.hasMore, loading: false);
    } catch (e) {
      if (gen != _generation) return;
      state = state.copyWith(loading: false, error: errorMessage(e));
    }
  }

  Future<void> loadMore() async {
    if (state.loading || state.loadingMore || !state.hasMore) return;
    final gen = _generation;
    state = state.copyWith(loadingMore: true);
    try {
      final page = await ref.read(ownerRepositoryProvider).venues(
            query: state.query,
            status: state.status,
            limit: AppConfig.pageSize,
            offset: state.items.length,
          );
      if (gen != _generation) return;
      state = state.copyWith(items: [...state.items, ...page.items], hasMore: page.hasMore, loadingMore: false);
    } catch (e) {
      if (gen != _generation) return;
      state = state.copyWith(loadingMore: false, error: errorMessage(e));
    }
  }

  void setQuery(String q) {
    if (q == state.query) return;
    state = state.copyWith(query: q);
    refresh();
  }

  void setStatus(String? status) {
    if (status == state.status) return;
    state = status == null ? state.copyWith(clearStatus: true) : state.copyWith(status: status);
    refresh();
  }
}

final venueListProvider = NotifierProvider<VenueListController, VenueListState>(VenueListController.new);

/// Call after any change to a venue so the list and the dashboard show fresh data.
void invalidateVenueData(WidgetRef ref) {
  ref.invalidate(venueListProvider);
  ref.invalidate(dashboardProvider);
}

class VenuesScreen extends ConsumerStatefulWidget {
  const VenuesScreen({super.key});

  @override
  ConsumerState<VenuesScreen> createState() => _VenuesScreenState();
}

class _VenuesScreenState extends ConsumerState<VenuesScreen> {
  final _scroll = ScrollController();
  final _search = TextEditingController();
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels > _scroll.position.maxScrollExtent - 300) {
        ref.read(venueListProvider.notifier).loadMore();
      }
    });
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _scroll.dispose();
    _search.dispose();
    super.dispose();
  }

  void _onSearch(String text) {
    _debounce?.cancel();
    _debounce = Timer(AppConfig.searchDebounce, () => ref.read(venueListProvider.notifier).setQuery(text.trim()));
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(venueListProvider);
    final controller = ref.read(venueListProvider.notifier);
    final dash = ref.watch(dashboardProvider).valueOrNull;
    String chip(String label, int? count) => count == null ? label : '$label ($count)';
    final counts = <String?, int?>{
      null: dash?.venuesTotal,
      'published': dash?.venuesPublished,
      'draft': dash?.venuesDraft,
      'archived': dash == null ? null : (dash.venuesTotal - dash.venuesPublished - dash.venuesDraft),
    };

    return Scaffold(
      appBar: AppBar(title: const Text('My Venues'), titleSpacing: Gap.page),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push('/owner/venues/new'),
        icon: const Icon(Icons.add_rounded),
        label: const Text('Add venue', style: TextStyle(fontWeight: FontWeight.w700)),
      ),
      body: ResponsivePage(
        maxWidth: 720,
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: TextField(
                controller: _search,
                onChanged: _onSearch,
                textInputAction: TextInputAction.search,
                decoration: InputDecoration(
                  hintText: 'Search your venues',
                  filled: true,
                  fillColor: Theme.of(context).colorScheme.surface,
                  prefixIcon: const Icon(Icons.search_rounded),
                  suffixIcon: _search.text.isEmpty
                      ? null
                      : IconButton(
                          icon: const Icon(Icons.close_rounded),
                          onPressed: () {
                            _search.clear();
                            controller.setQuery('');
                            setState(() {});
                          },
                        ),
                ),
              ),
            ),
            SizedBox(
              height: 52,
              child: ListView(
                scrollDirection: Axis.horizontal,
                children: [
                  for (final (label, value) in const [('All', null), ('Published', 'published'), ('Drafts', 'draft'), ('Archived', 'archived')])
                    Padding(
                      padding: const EdgeInsets.only(right: 8, top: 8, bottom: 8),
                      child: ChoiceChip(
                        label: Text(chip(label, counts[value])),
                        showCheckmark: false,
                        selected: state.status == value,
                        selectedColor: Theme.of(context).colorScheme.primary,
                        labelStyle: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          color: state.status == value ? Colors.white : Theme.of(context).colorScheme.onSurface,
                        ),
                        onSelected: (_) => controller.setStatus(value),
                      ),
                    ),
                ],
              ),
            ),
            Expanded(child: _body(context, state, controller)),
          ],
        ),
      ),
    );
  }

  Widget _body(BuildContext context, VenueListState state, VenueListController controller) {
    if (state.loading && state.items.isEmpty) {
      return ListView(
        children: List.generate(3, (_) => const Padding(padding: EdgeInsets.only(bottom: 12), child: ShimmerBox(height: 112, radius: Radii.card))),
      );
    }
    if (state.error != null && state.items.isEmpty) {
      return ErrorView(message: state.error!, onRetry: controller.refresh);
    }
    if (state.items.isEmpty) {
      return state.filtered
          ? const EmptyState(icon: Icons.search_off_rounded, title: 'No venues match', message: 'Try a different name or filter.')
          : EmptyState(
              icon: Icons.storefront_rounded,
              title: 'No venues yet',
              message: 'Add your first venue to start getting discovered.',
              actionLabel: 'Add venue',
              onAction: () => context.push('/owner/venues/new'),
            );
    }
    return RefreshIndicator(
      onRefresh: controller.refresh,
      child: ListView.separated(
        controller: _scroll,
        padding: const EdgeInsets.only(bottom: 96, top: 4),
        itemCount: state.items.length + (state.hasMore || state.loadingMore ? 1 : 0),
        separatorBuilder: (_, __) => const SizedBox(height: Gap.md),
        itemBuilder: (context, i) {
          if (i >= state.items.length) {
            return const Padding(padding: EdgeInsets.all(16), child: Center(child: CircularProgressIndicator()));
          }
          return VenueCard(venue: state.items[i]);
        },
      ),
    );
  }
}

class VenueCard extends StatelessWidget {
  const VenueCard({super.key, required this.venue});
  final OwnerVenueCard venue;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final location = joinLocation(venue.addressLine, venue.cityName).ifEmpty('Location not set');
    return OwnerCard(
      padding: const EdgeInsets.all(Gap.md),
      onTap: () => context.push('/owner/venues/${venue.id}'),
      child: Row(
        children: [
          SizedBox(width: 92, height: 92, child: ZNetworkImage(url: venue.coverImageUrl, borderRadius: 14, semanticLabel: venue.name)),
          const SizedBox(width: Gap.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  Expanded(
                    flex: 3,
                    child: Text(venue.name, maxLines: 1, overflow: TextOverflow.ellipsis, style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
                  ),
                  const SizedBox(width: 6),
                  Flexible(flex: 2, child: StatusChip(venue.status)),
                ]),
                const SizedBox(height: 4),
                Row(children: [
                  const Icon(Icons.location_on_outlined, size: 15, color: ZuruvColors.textSecondary),
                  const SizedBox(width: 3),
                  Expanded(
                    child: Text(location, maxLines: 1, overflow: TextOverflow.ellipsis, style: theme.textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary)),
                  ),
                ]),
                const SizedBox(height: 8),
                Row(children: [
                  Expanded(child: Align(alignment: Alignment.centerLeft, child: RatingText(rating: venue.ratingAvg, count: venue.ratingCount))),
                  const SizedBox(width: 8),
                  Flexible(
                    child: FittedBox(
                      fit: BoxFit.scaleDown,
                      alignment: Alignment.centerRight,
                      child: Text(
                        venue.startingPricePaise == null ? 'Price not set' : 'From ${formatMoney(venue.startingPricePaise!, currency: venue.currency)}/hr',
                        maxLines: 1,
                        style: theme.textTheme.bodySmall?.copyWith(fontWeight: FontWeight.w800, color: theme.colorScheme.onSurface),
                      ),
                    ),
                  ),
                ]),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

extension on String {
  String ifEmpty(String fallback) => isEmpty ? fallback : this;
}
