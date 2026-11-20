import 'package:flutter/material.dart';
import 'package:zuruv/core/maps/location_picker_screen.dart';
import 'package:zuruv/customer/features/location/location_service.dart' show GeoPoint;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_shared/flutter_shared.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import 'package:zuruv/core/config/app_config.dart';
import 'package:zuruv/core/constants/tokens.dart';
import 'package:zuruv/core/network/api_helpers.dart';
import 'package:zuruv/owner/shared/models/models.dart';
import 'package:zuruv/owner/shared/repositories/owner_repository.dart';
import 'package:zuruv/owner/shared/widgets/common_widgets.dart';
import 'package:zuruv/owner/shared/widgets/z_network_image.dart';
import 'package:zuruv/owner/features/venues/venue_manage_screen.dart';
import 'package:zuruv/owner/features/venue_form/address_search_dialog.dart';
import 'package:zuruv/owner/features/venues/venues_screen.dart';

/// Hands a picked photo to the form. Replaced in tests so no real picker is needed.
abstract class PhotoPicker {
  Future<PickedPhoto?> pick();
}

class PickedPhoto {
  const PickedPhoto({required this.name, required this.bytes});
  final String name;
  final List<int> bytes;
}

class GalleryPhotoPicker implements PhotoPicker {
  const GalleryPhotoPicker();
  @override
  Future<PickedPhoto?> pick() async {
    final file = await ImagePicker().pickImage(source: ImageSource.gallery, maxWidth: 2048, maxHeight: 2048, imageQuality: 88);
    if (file == null) return null;
    return PickedPhoto(name: file.name, bytes: await file.readAsBytes());
  }
}

final photoPickerProvider = Provider<PhotoPicker>((ref) => const GalleryPhotoPicker());

/// Add / Edit venue. A new venue is saved as a draft first (only the name is required), which
/// unlocks photo upload because photos belong to a saved venue. Publishing has its own checks.
class VenueFormScreen extends ConsumerStatefulWidget {
  const VenueFormScreen({super.key, this.venueId});
  final String? venueId;

  @override
  ConsumerState<VenueFormScreen> createState() => _VenueFormScreenState();
}

class _VenueFormScreenState extends ConsumerState<VenueFormScreen> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _description = TextEditingController();
  final _address = TextEditingController();
  final _postal = TextEditingController();
  final _lat = TextEditingController();
  final _lng = TextEditingController();
  final _phone = TextEditingController();
  final _price = TextEditingController();

  String? _id;
  String? _cityId;
  Set<String> _categories = {};
  Set<String> _amenities = {};
  List<VenueImage> _images = [];
  OwnerVenueDetail? _saved;
  bool _loading = false;
  bool _saving = false;
  bool _uploading = false;
  String? _error;
  String? _loadError;

  bool get _isEdit => _id != null;

  @override
  void initState() {
    super.initState();
    _id = widget.venueId;
    if (_id != null) _load();
  }

  @override
  void dispose() {
    for (final c in [_name, _description, _address, _postal, _lat, _lng, _phone, _price]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _loadError = null;
    });
    try {
      final v = await ref.read(ownerRepositoryProvider).venue(_id!);
      if (!mounted) return;
      _apply(v);
      setState(() => _loading = false);
    } catch (e) {
      if (mounted) {
        setState(() {
          _loading = false;
          _loadError = errorMessage(e);
        });
      }
    }
  }

  void _apply(OwnerVenueDetail v) {
    _saved = v;
    _name.text = v.name;
    _description.text = v.description ?? '';
    _address.text = v.card.addressLine ?? '';
    _postal.text = v.postalCode ?? '';
    _lat.text = v.latitude?.toString() ?? '';
    _lng.text = v.longitude?.toString() ?? '';
    _phone.text = v.contactPhone ?? '';
    _price.text = v.card.startingPricePaise == null ? '' : (v.card.startingPricePaise! ~/ 100).toString();
    _cityId = v.cityId;
    _categories = v.categoryIds.toSet();
    _amenities = v.amenityIds.toSet();
    _images = v.images;
  }

  String? _opt(TextEditingController c) {
    final t = c.text.trim();
    return t.isEmpty ? null : t;
  }

  /// Builds the request body. Optional text fields that were emptied are sent as null so they are
  /// cleared; fields never touched are left out.
  VenueDraft _draft() {
    final clear = <String>{};
    void check(String key, TextEditingController c, Object? before) {
      if (_isEdit && c.text.trim().isEmpty && before != null) clear.add(key);
    }

    final s = _saved;
    check('description', _description, s?.description);
    check('address_line', _address, s?.card.addressLine);
    check('postal_code', _postal, s?.postalCode);
    check('contact_phone', _phone, s?.contactPhone);
    check('starting_price_paise', _price, s?.card.startingPricePaise);
    final lat = double.tryParse(_lat.text.trim());
    final lng = double.tryParse(_lng.text.trim());
    if (_isEdit && lat == null && lng == null && s?.latitude != null) clear.addAll({'latitude', 'longitude'});
    if (_isEdit && _cityId == null && s?.cityId != null) clear.add('city_id');
    final rupees = int.tryParse(_price.text.trim());
    return VenueDraft(
      name: _name.text.trim(),
      description: _opt(_description),
      addressLine: _opt(_address),
      cityId: _cityId,
      postalCode: _opt(_postal),
      latitude: lat,
      longitude: lng,
      contactPhone: _opt(_phone),
      startingPricePaise: rupees == null ? null : rupees * 100,
      categoryIds: _categories.toList(),
      amenityIds: _amenities.toList(),
      clear: clear,
    );
  }

  Future<bool> _save() async {
    if (!_form.currentState!.validate()) return false;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final repo = ref.read(ownerRepositoryProvider);
      final v = _isEdit ? await repo.updateVenue(_id!, _draft()) : await repo.createVenue(_draft());
      if (!mounted) return false;
      final wasNew = !_isEdit;
      _id = v.id;
      _saved = v;
      _images = v.images;
      invalidateVenueData(ref);
      ref.invalidate(venueDetailProvider(v.id));
      setState(() {});
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(wasNew ? 'Draft saved. You can now add photos.' : 'Venue updated'),
      ));
      return true;
    } on ApiException catch (e) {
      setState(() => _error = e.details is List ? '${e.message}\n${(e.details as List).join('\n')}' : e.message);
      return false;
    } catch (e) {
      setState(() => _error = errorMessage(e));
      return false;
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _saveAndPublish() async {
    if (!await _save() || !mounted) return;
    try {
      await ref.read(ownerRepositoryProvider).publish(_id!);
      invalidateVenueData(ref);
      ref.invalidate(venueDetailProvider(_id!));
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Venue published')));
      context.pop();
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.details is List ? '${e.message}\n${(e.details as List).join('\n')}' : e.message);
    } catch (e) {
      if (mounted) setState(() => _error = errorMessage(e));
    }
  }

  // ------------------------------------------------------------------ photos
  Future<void> _refreshImages() async {
    final v = await ref.read(ownerRepositoryProvider).venue(_id!);
    if (!mounted) return;
    setState(() {
      _saved = v;
      _images = v.images;
    });
    invalidateVenueData(ref);
    ref.invalidate(venueDetailProvider(_id!));
  }

  Future<void> _addPhoto() async {
    if (_images.length >= AppConfig.venueImageMaxCount) {
      setState(() => _error = 'A venue can have at most ${AppConfig.venueImageMaxCount} photos.');
      return;
    }
    PickedPhoto? photo;
    try {
      photo = await ref.read(photoPickerProvider).pick();
    } catch (_) {
      setState(() => _error = 'Could not open your photos. Check the app has permission.');
      return;
    }
    if (photo == null) return;
    final dot = photo.name.lastIndexOf('.');
    final ext = dot < 0 ? '' : photo.name.substring(dot + 1).toLowerCase();
    if (!AppConfig.imageExtensions.contains(ext)) {
      setState(() => _error = 'Choose a JPG, PNG or WebP image.');
      return;
    }
    if (photo.bytes.length > AppConfig.venueImageMaxBytes) {
      setState(() => _error = 'That image is larger than 5 MB. Choose a smaller one.');
      return;
    }
    setState(() {
      _uploading = true;
      _error = null;
    });
    try {
      await ref.read(ownerRepositoryProvider).uploadImage(_id!, bytes: photo.bytes, filename: photo.name);
      await _refreshImages();
    } catch (e) {
      if (mounted) setState(() => _error = errorMessage(e));
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  Future<void> _imageAction(Future<void> Function() action) async {
    setState(() {
      _uploading = true;
      _error = null;
    });
    try {
      await action();
      await _refreshImages();
    } catch (e) {
      if (mounted) setState(() => _error = errorMessage(e));
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  Future<void> _move(int index, int delta) {
    final ids = _images.map((i) => i.id).toList();
    final target = index + delta;
    if (target < 0 || target >= ids.length) return Future.value();
    final item = ids.removeAt(index);
    ids.insert(target, item);
    return _imageAction(() => ref.read(ownerRepositoryProvider).reorderImages(_id!, ids));
  }

  Future<void> _photoMenu(int index) async {
    final image = _images[index];
    final choice = await showModalBottomSheet<String>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          if (!image.isCover) ListTile(leading: const Icon(Icons.star_outline_rounded), title: const Text('Set as cover'), onTap: () => Navigator.pop(ctx, 'cover')),
          if (index > 0) ListTile(leading: const Icon(Icons.arrow_back_rounded), title: const Text('Move earlier'), onTap: () => Navigator.pop(ctx, 'left')),
          if (index < _images.length - 1) ListTile(leading: const Icon(Icons.arrow_forward_rounded), title: const Text('Move later'), onTap: () => Navigator.pop(ctx, 'right')),
          ListTile(
            leading: const Icon(Icons.delete_outline_rounded, color: ZuruvColors.error),
            title: const Text('Remove photo', style: TextStyle(color: ZuruvColors.error)),
            onTap: () => Navigator.pop(ctx, 'remove'),
          ),
        ]),
      ),
    );
    switch (choice) {
      case 'cover':
        await _imageAction(() => ref.read(ownerRepositoryProvider).setCover(_id!, image.id));
      case 'left':
        await _move(index, -1);
      case 'right':
        await _move(index, 1);
      case 'remove':
        await _imageAction(() => ref.read(ownerRepositoryProvider).deleteImage(_id!, image.id));
    }
  }

  // ------------------------------------------------------------------ build
  Future<void> _searchAddress() async {
    final d = await showAddressSearch(context);
    if (d == null || !mounted) return;
    setState(() {
      if (d.formattedAddress != null) _address.text = d.formattedAddress!;
      if (d.postalCode != null) _postal.text = d.postalCode!;
      if (d.latitude != null) _lat.text = d.latitude!.toString();
      if (d.longitude != null) _lng.text = d.longitude!.toString();
    });
  }

  Future<void> _pickOnMap() async {
    final lat = double.tryParse(_lat.text.trim());
    final lng = double.tryParse(_lng.text.trim());
    final point = await pickLocationOnMap(context, initial: lat == null || lng == null ? null : GeoPoint(lat, lng));
    if (point == null || !mounted) return;
    setState(() {
      _lat.text = point.lat.toStringAsFixed(6);
      _lng.text = point.lng.toStringAsFixed(6);
    });
  }

  String? _latValidator(String? v) {
    final text = (v ?? '').trim();
    if (text.isEmpty) return _lng.text.trim().isEmpty ? null : 'Enter latitude too';
    final d = double.tryParse(text);
    return d == null || d < -90 || d > 90 ? 'Between -90 and 90' : null;
  }

  String? _lngValidator(String? v) {
    final text = (v ?? '').trim();
    if (text.isEmpty) return _lat.text.trim().isEmpty ? null : 'Enter longitude too';
    final d = double.tryParse(text);
    return d == null || d < -180 || d > 180 ? 'Between -180 and 180' : null;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cities = ref.watch(citiesProvider);
    final categories = ref.watch(categoriesProvider);
    final amenities = ref.watch(amenitiesProvider);
    final busy = _saving || _uploading;

    if (_loading) return Scaffold(appBar: AppBar(title: const Text('Edit venue')), body: const LoadingView());
    if (_loadError != null) {
      return Scaffold(appBar: AppBar(title: const Text('Edit venue')), body: ErrorView(message: _loadError!, onRetry: _load));
    }

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(icon: const Icon(Icons.close_rounded), onPressed: busy ? null : () => context.pop()),
        title: Text(_isEdit ? 'Edit venue' : 'Add venue'),
      ),
      body: SafeArea(
        child: ResponsivePage(
          maxWidth: 640,
          child: Form(
            key: _form,
            child: ListView(
              padding: const EdgeInsets.symmetric(vertical: 12),
              children: [
                if (_error != null) ...[AuthBanner(message: _error!), const SizedBox(height: Gap.lg)],
                const SectionHeader('Basics'),
                TextFormField(
                  controller: _name,
                  textCapitalization: TextCapitalization.words,
                  maxLength: 120,
                  decoration: const InputDecoration(labelText: 'Venue name'),
                  validator: (v) => Validators.required(v, 'the venue name'),
                ),
                const SizedBox(height: Gap.sm),
                TextFormField(
                  controller: _description,
                  minLines: 3,
                  maxLines: 6,
                  maxLength: 2000,
                  textCapitalization: TextCapitalization.sentences,
                  decoration: const InputDecoration(labelText: 'Description (optional)', alignLabelWithHint: true),
                ),
                const SectionHeader('Sports'),
                categories.when(
                  loading: () => const LinearProgressIndicator(),
                  error: (e, _) => Text(errorMessage(e), style: const TextStyle(color: ZuruvColors.error)),
                  data: (list) => Wrap(spacing: 8, runSpacing: 6, children: [
                    for (final c in list)
                      FilterChip(
                        label: Text(c.name),
                        selected: _categories.contains(c.id),
                        onSelected: (on) => setState(() => on ? _categories.add(c.id) : _categories.remove(c.id)),
                      ),
                  ]),
                ),
                const SectionHeader('Location'),
                cities.when(
                  loading: () => const LinearProgressIndicator(),
                  error: (e, _) => Text(errorMessage(e), style: const TextStyle(color: ZuruvColors.error)),
                  data: (list) => DropdownButtonFormField<String>(
                    initialValue: list.any((c) => c.id == _cityId) ? _cityId : null,
                    isExpanded: true,
                    decoration: const InputDecoration(labelText: 'City'),
                    items: [for (final c in list) DropdownMenuItem(value: c.id, child: Text(c.label))],
                    onChanged: (v) => setState(() => _cityId = v),
                  ),
                ),
                const SizedBox(height: Gap.lg),
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed: _searchAddress,
                    icon: const Icon(Icons.search),
                    label: const Text('Search address'),
                  ),
                ),
                TextFormField(
                  controller: _address,
                  textCapitalization: TextCapitalization.words,
                  decoration: const InputDecoration(labelText: 'Address (optional)'),
                ),
                const SizedBox(height: Gap.lg),
                TextFormField(
                  controller: _postal,
                  keyboardType: TextInputType.text,
                  decoration: const InputDecoration(labelText: 'Postal code (optional)'),
                ),
                const SizedBox(height: Gap.lg),
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed: _pickOnMap,
                    icon: const Icon(Icons.pin_drop_outlined),
                    label: const Text('Pick on map'),
                  ),
                ),
                Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Expanded(
                    child: TextFormField(
                      controller: _lat,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
                      decoration: const InputDecoration(labelText: 'Latitude'),
                      validator: _latValidator,
                    ),
                  ),
                  const SizedBox(width: Gap.md),
                  Expanded(
                    child: TextFormField(
                      controller: _lng,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
                      decoration: const InputDecoration(labelText: 'Longitude'),
                      validator: _lngValidator,
                    ),
                  ),
                ]),
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text('Needed to publish, so customers can find the venue near them.',
                      style: theme.textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary)),
                ),
                const SectionHeader('Pricing & contact'),
                TextFormField(
                  controller: _price,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Starting price per hour (₹, optional)', prefixText: '₹ '),
                  validator: (v) {
                    final t = (v ?? '').trim();
                    if (t.isEmpty) return null;
                    final n = int.tryParse(t);
                    return n == null || n < 0 || n > 10000000 ? 'Enter a whole number of rupees' : null;
                  },
                ),
                const SizedBox(height: Gap.lg),
                TextFormField(
                  controller: _phone,
                  keyboardType: TextInputType.phone,
                  decoration: const InputDecoration(labelText: 'Contact phone (optional)', hintText: '+919876543210'),
                  validator: (v) => (v == null || v.trim().isEmpty) ? null : Validators.phone(v),
                ),
                const SectionHeader('Facilities & amenities'),
                amenities.when(
                  loading: () => const LinearProgressIndicator(),
                  error: (e, _) => Text(errorMessage(e), style: const TextStyle(color: ZuruvColors.error)),
                  data: (list) => list.isEmpty
                      ? Text('No amenities have been set up yet.', style: theme.textTheme.bodySmall)
                      : Wrap(spacing: 8, runSpacing: 6, children: [
                          for (final a in list)
                            FilterChip(
                              label: Text(a.name),
                              selected: _amenities.contains(a.id),
                              onSelected: (on) => setState(() => on ? _amenities.add(a.id) : _amenities.remove(a.id)),
                            ),
                        ]),
                ),
                const SectionHeader('Photos'),
                _isEdit ? _photoGrid(theme) : _photosLocked(theme),
                const SizedBox(height: 28),
                LoadingButton(label: _isEdit ? 'Save changes' : 'Save draft', loading: _saving, onPressed: busy ? null : _save),
                const SizedBox(height: Gap.md),
                OutlinedButton(onPressed: busy ? null : _saveAndPublish, child: const Text('Save & publish')),
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    'Publishing needs a city, location and at least one sport. Listings go live straight away; admin approval is not set up yet.',
                    style: theme.textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary),
                    textAlign: TextAlign.center,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _photosLocked(ThemeData theme) => Container(
        padding: const EdgeInsets.all(Gap.lg),
        decoration: BoxDecoration(color: Theme.of(context).colorScheme.primaryContainer, borderRadius: BorderRadius.circular(Radii.card)),
        child: Row(children: [
          Icon(Icons.photo_library_outlined, color: theme.colorScheme.primary),
          const SizedBox(width: Gap.md),
          const Expanded(child: Text('Save the draft first, then add photos.')),
        ]),
      );

  Widget _photoGrid(ThemeData theme) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        GridView.count(
          crossAxisCount: 3,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 8,
          crossAxisSpacing: 8,
          children: [
            for (var i = 0; i < _images.length; i++)
              GestureDetector(
                key: ValueKey('photo-${_images[i].id}'),
                onTap: _uploading ? null : () => _photoMenu(i),
                child: Stack(fit: StackFit.expand, children: [
                  ZNetworkImage(url: _images[i].url, borderRadius: 12, semanticLabel: _images[i].altText ?? 'Venue photo ${i + 1}'),
                  if (_images[i].isCover)
                    Positioned(
                      left: 6,
                      top: 6,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(color: theme.colorScheme.primary, borderRadius: BorderRadius.circular(10)),
                        child: const Text('Cover', style: TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w700)),
                      ),
                    ),
                ]),
              ),
            if (_images.length < AppConfig.venueImageMaxCount)
              InkWell(
                key: const ValueKey('add-photo'),
                borderRadius: BorderRadius.circular(12),
                onTap: _uploading ? null : _addPhoto,
                child: Container(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Theme.of(context).colorScheme.outline),
                    color: Theme.of(context).colorScheme.primaryContainer,
                  ),
                  child: _uploading
                      ? const Center(child: SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2)))
                      : Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                          Icon(Icons.add_photo_alternate_outlined, color: theme.colorScheme.primary),
                          const SizedBox(height: 4),
                          Text('Add photo', style: TextStyle(color: theme.colorScheme.primary, fontWeight: FontWeight.w600, fontSize: 12)),
                        ]),
                ),
              ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          'Tap a photo to set the cover, reorder or remove it. JPG, PNG or WebP, up to 5 MB, ${AppConfig.venueImageMaxCount} photos.',
          style: theme.textTheme.bodySmall?.copyWith(color: ZuruvColors.textSecondary),
        ),
      ],
    );
  }
}
