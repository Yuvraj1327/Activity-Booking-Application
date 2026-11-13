import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/owner/shared/models/models.dart';
import 'package:zuruv/owner/shared/repositories/owner_repository.dart';

/// Search an address with the server's Places proxy and return its details (address, coordinates,
/// postal code). The result only fills the form; the owner still reviews it before saving.
Future<PlaceDetails?> showAddressSearch(BuildContext context) =>
    showDialog<PlaceDetails>(context: context, builder: (_) => const AddressSearchDialog());

class AddressSearchDialog extends ConsumerStatefulWidget {
  const AddressSearchDialog({super.key});

  @override
  ConsumerState<AddressSearchDialog> createState() => _AddressSearchDialogState();
}

class _AddressSearchDialogState extends ConsumerState<AddressSearchDialog> {
  final _query = TextEditingController();
  List<PlaceSuggestion> _results = const [];
  bool _busy = false;
  bool _searched = false;
  String? _error;

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    final q = _query.text.trim();
    if (q.length < 2) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final found = await ref.read(ownerRepositoryProvider).searchPlaces(q);
      if (!mounted) return;
      setState(() {
        _results = found;
        _searched = true;
        _busy = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = errorMessage(e);
        _busy = false;
      });
    }
  }

  Future<void> _pick(PlaceSuggestion s) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final d = await ref.read(ownerRepositoryProvider).placeDetails(s.placeId);
      if (!mounted) return;
      Navigator.of(context).pop(d);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = errorMessage(e);
        _busy = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Search address'),
      content: SizedBox(
        width: 420,
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          TextField(
            controller: _query,
            autofocus: true,
            textInputAction: TextInputAction.search,
            onSubmitted: (_) => _search(),
            decoration: InputDecoration(
              labelText: 'Venue address or landmark',
              suffixIcon: IconButton(
                tooltip: 'Search',
                icon: const Icon(Icons.search),
                onPressed: _busy ? null : _search,
              ),
            ),
          ),
          const SizedBox(height: 12),
          if (_busy) const Center(child: Padding(padding: EdgeInsets.all(8), child: CircularProgressIndicator())),
          if (_error != null) Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          if (_searched && _results.isEmpty && _error == null && !_busy) const Text('No matching places found.'),
          if (_results.isNotEmpty)
            Flexible(
              child: ListView(shrinkWrap: true, children: [
                for (final r in _results)
                  ListTile(
                    leading: const Icon(Icons.place_outlined),
                    title: Text(r.description),
                    onTap: _busy ? null : () => _pick(r),
                  ),
              ]),
            ),
        ]),
      ),
      actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel'))],
    );
  }
}
