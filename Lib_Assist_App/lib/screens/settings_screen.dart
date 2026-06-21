import 'package:flutter/material.dart';
import '../theme/colors.dart';
import '../services/api_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _formKey = GlobalKey<FormState>();
  final _urlCtrl = TextEditingController();
  final _keyCtrl = TextEditingController();

  bool _isTesting = false;
  bool? _testResult; // null = not tested, true = success, false = fail
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _urlCtrl.text = ApiService.baseUrl;
    _keyCtrl.text = ApiService.apiKey;
  }

  Future<void> _runConnectionTest() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isTesting = true;
      _testResult = null;
    });

    final String testUrl = _urlCtrl.text.trim();
    final String testKey = _keyCtrl.text.trim();

    final bool isOk = await ApiService.testConnection(testUrl, testKey);

    setState(() {
      _isTesting = false;
      _testResult = isOk;
    });
  }

  Future<void> _saveSettings() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isSaving = true;
    });

    try {
      final String finalUrl = _urlCtrl.text.trim();
      final String finalKey = _keyCtrl.text.trim();

      await ApiService.updateConnectionSettings(finalUrl, finalKey);

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Connection configuration saved successfully!"),
          backgroundColor: AppColors.success,
        ),
      );
      Navigator.pop(context, true); // Pop with true to reload parent screens
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("Error saving settings: $e"),
          backgroundColor: AppColors.danger,
        ),
      );
    } finally {
      setState(() {
        _isSaving = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('⚙️ Connection Settings'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Banner info
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                margin: const EdgeInsets.bottom(24),
                decoration: BoxDecoration(
                  color: AppColors.primary.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppColors.primary.withOpacity(0.2)),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.settings_input_component_rounded, color: AppColors.primary),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        "Configure the endpoint of your PythonAnywhere server and authentication credentials to establish secure RPC communication.",
                        style: TextStyle(fontSize: 12, height: 1.3, color: AppColors.textSecondary),
                      ),
                    ),
                  ],
                ),
              ),

              // Server URL Field
              const Text(
                'Server Endpoint URL',
                style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 14),
              ),
              const SizedBox(height: 8),
              TextFormField(
                controller: _urlCtrl,
                keyboardType: TextInputType.url,
                decoration: const InputDecoration(
                  hintText: 'https://username.pythonanywhere.com',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.dns_rounded),
                ),
                validator: (val) {
                  if (val == null || val.trim().isEmpty) {
                    return 'Server URL cannot be empty';
                  }
                  if (!val.startsWith('http://') && !val.startsWith('https://')) {
                    return 'URL must start with http:// or https://';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 20),

              // API Key Field
              const Text(
                'X-API-Key Credentials',
                style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 14),
              ),
              const SizedBox(height: 8),
              TextFormField(
                controller: _keyCtrl,
                obscureText: true,
                decoration: const InputDecoration(
                  hintText: 'Enter API Access Key',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.vpn_key_rounded),
                ),
                validator: (val) {
                  if (val == null || val.trim().isEmpty) {
                    return 'API Key cannot be empty';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 24),

              // Test Connection result display
              if (_testResult != null) ...[
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: (_testResult! ? AppColors.success : AppColors.danger).withOpacity(0.08),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: (_testResult! ? AppColors.success : AppColors.danger).withOpacity(0.3),
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        _testResult! ? Icons.check_circle_rounded : Icons.cancel_rounded,
                        color: _testResult! ? AppColors.success : AppColors.danger,
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          _testResult!
                              ? "Connection Successful! Server is reachable and authorized."
                              : "Connection Failed! Please verify your URL endpoint, API key, and internet connection.",
                          style: TextStyle(
                            color: _testResult! ? AppColors.success : AppColors.danger,
                            fontWeight: FontWeight.bold,
                            fontSize: 13,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
              ],

              // Action buttons: Test Connection
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _isTesting ? null : _runConnectionTest,
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppColors.primary,
                        side: const BorderSide(color: AppColors.primary),
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      icon: _isTesting
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.primary),
                            )
                          : const Icon(Icons.wifi_tethering_rounded, size: 18),
                      label: const Text('Test Connection', style: TextStyle(fontWeight: FontWeight.bold)),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),

              // Save button
              SizedBox(
                width: double.infinity,
                height: 52,
                child: ElevatedButton(
                  onPressed: _isSaving ? null : _saveSettings,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.accent,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                  child: _isSaving
                      ? const SizedBox(
                          width: 24,
                          height: 24,
                          child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                        )
                      : const Text(
                          'Save Configuration',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
