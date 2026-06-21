import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:image_picker/image_picker.dart';
import '../theme/colors.dart';
import '../services/api_service.dart';

class StudentFormScreen extends StatefulWidget {
  final int? studentId; // If null, we are in ADD mode. Otherwise EDIT mode.

  const StudentFormScreen({
    super.key,
    this.studentId,
  });

  @override
  State<StudentFormScreen> createState() => _StudentFormScreenState();
}

class _StudentFormScreenState extends State<StudentFormScreen> {
  final _formKey = GlobalKey<FormState>();
  bool _isLoading = false;
  bool _isSaving = false;
  String? _errorMessage;

  // Controllers
  final _nameCtrl = TextEditingController();
  final _mobileCtrl = TextEditingController();
  final _feeCtrl = TextEditingController();
  String _selectedShift = 'FULL_DAY';
  String? _selectedSeat;
  String _selectedDateStr = DateFormat('yyyy-MM-dd').format(DateTime.now());

  // Dropdowns lists
  List<String> _compatibleSeats = [];
  String? _initialSeat; // To preserve current seat when editing

  // Photo state
  XFile? _pickedPhotoFile;
  Uint8List? _pickedPhotoBytes;
  String? _existingPhotoUrl; // Photo URL from server (edit mode)
  bool _isUploadingPhoto = false;

  final List<Map<String, String>> _shifts = [
    {'value': 'FULL_DAY', 'label': 'Full Day (24 hrs)'},
    {'value': 'HALF_DAY_DAY', 'label': 'Half Day - Day (6 AM - 6 PM)'},
    {'value': 'HALF_DAY_NIGHT', 'label': 'Half Day - Night (6 PM - 6 AM)'},
  ];

  @override
  void initState() {
    super.initState();
    if (widget.studentId != null) {
      _loadStudentData();
    } else {
      _loadCompatibleSeats();
    }
  }

  Future<void> _loadStudentData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final student = await ApiService.getStudentById(widget.studentId!);
      if (student == null) throw Exception("Student not found.");

      final fees = await ApiService.getFeeRecord(widget.studentId!);

      setState(() {
        _nameCtrl.text = student['full_name'] ?? '';
        _mobileCtrl.text = student['mobile_number'] ?? '';
        _selectedShift = student['shift_type'] ?? 'FULL_DAY';
        _initialSeat = student['seat_number'];
        _selectedDateStr = student['admission_date'] ?? DateFormat('yyyy-MM-dd').format(DateTime.now());
        if (fees != null) {
          final double monthly = double.parse((fees['monthly_fee'] ?? 0).toString());
          _feeCtrl.text = monthly.toStringAsFixed(0);
        }

        // Load existing photo URL
        final photoPath = student['photo_path']?.toString();
        _existingPhotoUrl = ApiService.getStudentPhotoUrl(photoPath);
      });

      // Load seats compatible with current shift
      await _loadCompatibleSeats();

      // Ensure the initial seat is selected and included in the dropdown options
      setState(() {
        if (_initialSeat != null && !_compatibleSeats.contains(_initialSeat)) {
          _compatibleSeats.add(_initialSeat!);
          _compatibleSeats.sort();
        }
        _selectedSeat = _initialSeat;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = "Failed to load student details: $e";
        _isLoading = false;
      });
    }
  }

  Future<void> _loadCompatibleSeats() async {
    try {
      final seats = await ApiService.getCompatibleSeats(_selectedShift);
      setState(() {
        _compatibleSeats = seats;
        
        // If current seat is no longer compatible (i.e. shift changed), clear selection
        if (_selectedSeat != null && !_compatibleSeats.contains(_selectedSeat)) {
          // Exception: preserve initial seat if the shift matches initial shift
          if (widget.studentId != null && _selectedSeat == _initialSeat) {
            _compatibleSeats.add(_initialSeat!);
            _compatibleSeats.sort();
          } else {
            _selectedSeat = null;
          }
        }

        // Auto select first option if none is selected
        if (_selectedSeat == null && _compatibleSeats.isNotEmpty) {
          _selectedSeat = _compatibleSeats.first;
        }
      });
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("Failed to fetch compatible seats: $e"),
          backgroundColor: AppColors.danger,
        ),
      );
    }
  }

  Future<void> _pickPhoto(ImageSource source) async {
    try {
      final picker = ImagePicker();
      final XFile? picked = await picker.pickImage(
        source: source,
        maxWidth: 800,
        maxHeight: 800,
        imageQuality: 85,
      );
      if (picked != null) {
        final bytes = await picked.readAsBytes();
        setState(() {
          _pickedPhotoFile = picked;
          _pickedPhotoBytes = bytes;
        });
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("Could not pick image: $e"),
          backgroundColor: AppColors.danger,
        ),
      );
    }
  }

  void _showPhotoPickerSheet() {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.cardBg,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 40,
                height: 4,
                margin: const EdgeInsets.only(bottom: 16),
                decoration: BoxDecoration(
                  color: AppColors.textSecondary.withOpacity(0.3),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const Text(
                'Student Photo',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 16),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(Icons.camera_alt_rounded, color: AppColors.primary),
                ),
                title: const Text('Take Photo', style: TextStyle(color: AppColors.textPrimary)),
                subtitle: const Text('Use camera to capture', style: TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                onTap: () {
                  Navigator.pop(ctx);
                  _pickPhoto(ImageSource.camera);
                },
              ),
              ListTile(
                leading: Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppColors.accent.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(Icons.photo_library_rounded, color: AppColors.accent),
                ),
                title: const Text('Choose from Gallery', style: TextStyle(color: AppColors.textPrimary)),
                subtitle: const Text('Select existing photo', style: TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                onTap: () {
                  Navigator.pop(ctx);
                  _pickPhoto(ImageSource.gallery);
                },
              ),
              if (_pickedPhotoFile != null || _existingPhotoUrl != null)
                ListTile(
                  leading: Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppColors.danger.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(Icons.delete_outline_rounded, color: AppColors.danger),
                  ),
                  title: const Text('Remove Photo', style: TextStyle(color: AppColors.danger)),
                  subtitle: const Text('Clear selected photo', style: TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                  onTap: () {
                    Navigator.pop(ctx);
                    setState(() {
                      _pickedPhotoFile = null;
                      _existingPhotoUrl = null;
                    });
                  },
                ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _saveForm() async {
    if (!_formKey.currentState!.validate()) return;
    if (_selectedSeat == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Please allocate a seat for the student."),
          backgroundColor: AppColors.danger,
        ),
      );
      return;
    }

    setState(() {
      _isSaving = true;
    });

    try {
      final double feeVal = double.tryParse(_feeCtrl.text.trim()) ?? 0.0;
      final String nameVal = _nameCtrl.text.trim();
      final String mobileVal = _mobileCtrl.text.trim();

      Map<String, dynamic> response;
      int? savedStudentId = widget.studentId;

      if (widget.studentId == null) {
        // Add Mode
        response = await ApiService.addStudent(
          seatNumber: _selectedSeat!,
          fullName: nameVal,
          mobileNumber: mobileVal,
          admissionDate: _selectedDateStr,
          monthlyFee: feeVal,
          shiftType: _selectedShift,
        );
        if (response['success'] == true) {
          savedStudentId = response['student_id'];
        }
      } else {
        // Edit Mode
        response = await ApiService.updateStudent(
          studentId: widget.studentId!,
          fullName: nameVal,
          mobileNumber: mobileVal,
          admissionDate: _selectedDateStr,
          monthlyFee: feeVal,
          shiftType: _selectedShift,
        );
      }

      if (response['success'] == true) {
        // Upload photo if one was picked
        if (_pickedPhotoFile != null && savedStudentId != null) {
          setState(() {
            _isUploadingPhoto = true;
          });
          try {
            await ApiService.uploadStudentPhoto(savedStudentId, _pickedPhotoFile!);
          } catch (e) {
            // Show warning but don't block the save
            if (mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text("Profile saved, but photo upload failed: $e"),
                  backgroundColor: AppColors.warning,
                  duration: const Duration(seconds: 4),
                ),
              );
            }
          } finally {
            setState(() {
              _isUploadingPhoto = false;
            });
          }
        }

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(widget.studentId == null
                  ? "Student admitted successfully!"
                  : "Student profile updated successfully!"),
              backgroundColor: AppColors.success,
            ),
          );
          Navigator.pop(context, true); // Pop back and request list refresh
        }
      } else {
        throw Exception(response['message'] ?? "Operation failed.");
      }
    } catch (e) {
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text("Constraint Violation"),
          content: Text(e.toString().replaceAll("Exception: ", "")),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text("OK"),
            ),
          ],
        ),
      );
    } finally {
      setState(() {
        _isSaving = false;
      });
    }
  }

  Widget _buildPhotoSection() {
    final bool hasLocalPhoto = _pickedPhotoFile != null;
    final bool hasServerPhoto = _existingPhotoUrl != null;

    return Center(
      child: Column(
        children: [
          GestureDetector(
            onTap: _showPhotoPickerSheet,
            child: Stack(
              children: [
                // Avatar circle
                Container(
                  width: 120,
                  height: 120,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: hasLocalPhoto || hasServerPhoto
                        ? null
                        : LinearGradient(
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                            colors: [
                              AppColors.primary.withOpacity(0.15),
                              AppColors.accent.withOpacity(0.15),
                            ],
                          ),
                    border: Border.all(
                      color: hasLocalPhoto
                          ? AppColors.success.withOpacity(0.6)
                          : AppColors.primary.withOpacity(0.3),
                      width: 3,
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: (hasLocalPhoto ? AppColors.success : AppColors.primary).withOpacity(0.15),
                        blurRadius: 20,
                        offset: const Offset(0, 6),
                      ),
                    ],
                  ),
                  child: ClipOval(
                    child: hasLocalPhoto
                        ? Image.memory(
                            _pickedPhotoBytes!,
                            fit: BoxFit.cover,
                            width: 120,
                            height: 120,
                          )
                        : hasServerPhoto
                            ? Image.network(
                                _existingPhotoUrl!,
                                fit: BoxFit.cover,
                                width: 120,
                                height: 120,
                                errorBuilder: (_, __, ___) => _buildPhotoPlaceholder(),
                                loadingBuilder: (ctx, child, progress) {
                                  if (progress == null) return child;
                                  return Center(
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      color: AppColors.primary.withOpacity(0.5),
                                    ),
                                  );
                                },
                              )
                            : _buildPhotoPlaceholder(),
                  ),
                ),

                // Camera badge
                Positioned(
                  bottom: 0,
                  right: 0,
                  child: Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      color: AppColors.accent,
                      shape: BoxShape.circle,
                      border: Border.all(color: AppColors.cardBg, width: 3),
                      boxShadow: [
                        BoxShadow(
                          color: AppColors.accent.withOpacity(0.4),
                          blurRadius: 8,
                          offset: const Offset(0, 2),
                        ),
                      ],
                    ),
                    child: const Icon(Icons.camera_alt_rounded, size: 16, color: Colors.white),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),
          Text(
            hasLocalPhoto
                ? '📷 New photo selected'
                : hasServerPhoto
                    ? 'Tap to change photo'
                    : 'Tap to add photo',
            style: TextStyle(
              fontSize: 12,
              color: hasLocalPhoto ? AppColors.success : AppColors.textSecondary,
              fontWeight: hasLocalPhoto ? FontWeight.w600 : FontWeight.normal,
            ),
          ),
          if (_isUploadingPhoto)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: AppColors.primary.withOpacity(0.7),
                    ),
                  ),
                  const SizedBox(width: 8),
                  const Text(
                    'Uploading photo…',
                    style: TextStyle(fontSize: 11, color: AppColors.textSecondary),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildPhotoPlaceholder() {
    return Container(
      width: 120,
      height: 120,
      color: Colors.transparent,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.person_rounded, size: 44, color: AppColors.textSecondary.withOpacity(0.4)),
          const SizedBox(height: 4),
          Text(
            'Add Photo',
            style: TextStyle(fontSize: 10, color: AppColors.textSecondary.withOpacity(0.5)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final bool isEditMode = widget.studentId != null;

    if (_isLoading) {
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(color: AppColors.accent),
        ),
      );
    }

    if (_errorMessage != null) {
      return Scaffold(
        appBar: AppBar(title: Text(isEditMode ? 'Edit Profile' : 'New Admission')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline_rounded, color: AppColors.danger, size: 64),
                const SizedBox(height: 16),
                Text(
                  _errorMessage!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: AppColors.textPrimary, fontSize: 16),
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: isEditMode ? _loadStudentData : _loadCompatibleSeats,
                  child: const Text('Retry'),
                ),
              ],
            ),
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(isEditMode ? '✍️ Edit Student Profile' : '🎓 Student Admission'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Photo Section
              _buildPhotoSection(),
              const SizedBox(height: 24),

              // Banner info
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                margin: const EdgeInsets.only(bottom: 20),
                decoration: BoxDecoration(
                  color: AppColors.primary.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppColors.primary.withOpacity(0.2)),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.info_outline_rounded, color: AppColors.primary),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        isEditMode
                            ? "Make edits to student registration. Seat changes require modifying details directly in the desktop app."
                            : "Enter student details to allocate a library seat. Only compatible seats are selectable based on shift rules.",
                        style: const TextStyle(fontSize: 12, height: 1.3, color: AppColors.textSecondary),
                      ),
                    ),
                  ],
                ),
              ),

              // Full Name field
              TextFormField(
                controller: _nameCtrl,
                keyboardType: TextInputType.name,
                decoration: const InputDecoration(
                  labelText: 'Student Full Name',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.person_rounded),
                ),
                validator: (val) {
                  if (val == null || val.trim().isEmpty) {
                    return 'Please enter student name';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),

              // Mobile Number field
              TextFormField(
                controller: _mobileCtrl,
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(
                  labelText: 'Mobile Number',
                  hintText: '10-digit number',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.phone_android_rounded),
                ),
                validator: (val) {
                  if (val == null || val.trim().isEmpty) {
                    return 'Please enter mobile number';
                  }
                  final c = val.trim();
                  if (c.length < 10) {
                    return 'Please enter a valid 10-digit mobile number';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),

              // Shift Dropdown field
              DropdownButtonFormField<String>(
                value: _selectedShift,
                decoration: const InputDecoration(
                  labelText: 'Shift Allocation',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.access_time_filled_rounded),
                ),
                items: _shifts.map((s) {
                  return DropdownMenuItem(
                    value: s['value'],
                    child: Text(s['label'] ?? ''),
                  );
                }).toList(),
                onChanged: (val) {
                  if (val != null) {
                    setState(() {
                      _selectedShift = val;
                      _selectedSeat = null; // reset seat selection
                    });
                    _loadCompatibleSeats(); // reload list
                  }
                },
              ),
              const SizedBox(height: 16),

              // Seat Dropdown field
              DropdownButtonFormField<String>(
                value: _selectedSeat,
                decoration: InputDecoration(
                  labelText: isEditMode ? 'Seat Allocation' : 'Allocate Seat',
                  border: const OutlineInputBorder(),
                  prefixIcon: const Icon(Icons.chair_rounded),
                  helperText: _compatibleSeats.isEmpty
                      ? 'No seats available for this shift combination'
                      : '${_compatibleSeats.length} compatible seats found',
                ),
                items: _compatibleSeats.map((seat) {
                  final bool isCurrent = isEditMode && seat == _initialSeat;
                  return DropdownMenuItem(
                    value: seat,
                    child: Text(isCurrent ? '$seat (Current Seat)' : seat),
                  );
                }).toList(),
                onChanged: isEditMode
                    ? null // Disable seat shifting from phone to match desktop restrictions
                    : (val) {
                        setState(() {
                          _selectedSeat = val;
                        });
                      },
              ),
              const SizedBox(height: 16),

              // Monthly Fee field
              TextFormField(
                controller: _feeCtrl,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Monthly Fee (₹)',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.currency_rupee_rounded),
                ),
                validator: (val) {
                  if (val == null || val.trim().isEmpty) {
                    return 'Please enter monthly fee';
                  }
                  final d = double.tryParse(val);
                  if (d == null || d < 0) {
                    return 'Enter a valid fee (>= 0)';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),

              // Admission Date picker field
              InkWell(
                onTap: () async {
                  final initialDate = DateTime.tryParse(_selectedDateStr) ?? DateTime.now();
                  final picked = await showDatePicker(
                    context: context,
                    initialDate: initialDate,
                    firstDate: DateTime(2020),
                    lastDate: DateTime(2030),
                  );
                  if (picked != null) {
                    setState(() {
                      _selectedDateStr = DateFormat('yyyy-MM-dd').format(picked);
                    });
                  }
                },
                child: InputDecorator(
                  decoration: const InputDecoration(
                    labelText: 'Admission Date',
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.calendar_today_rounded),
                  ),
                  child: Text(
                    _selectedDateStr,
                    style: const TextStyle(fontSize: 16),
                  ),
                ),
              ),
              const SizedBox(height: 32),

              // Submit Button
              SizedBox(
                width: double.infinity,
                height: 52,
                child: ElevatedButton(
                  onPressed: _isSaving ? null : _saveForm,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.accent,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: _isSaving
                      ? const SizedBox(
                          width: 24,
                          height: 24,
                          child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                        )
                      : Text(
                          isEditMode ? 'Update Profile' : 'Complete Admission',
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
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
