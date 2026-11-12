import 'package:supabase_flutter/supabase_flutter.dart';

import '../config/app_env.dart';

/// Initialises Supabase (used for Auth only; all data goes through the ZURUV API).
/// Returns false, without throwing, when the environment is not configured.
Future<bool> initSupabase() async {
  if (!AppEnv.supabaseConfigured) return false;
  await Supabase.initialize(url: AppEnv.supabaseUrl, anonKey: AppEnv.supabaseAnonKey);
  return true;
}
