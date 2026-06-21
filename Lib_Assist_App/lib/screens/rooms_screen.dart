import 'package:flutter/material.dart';
import '../theme/colors.dart';
import '../services/api_service.dart';
import 'student_detail_screen.dart';
import 'student_form_screen.dart';

class RoomsScreen extends StatefulWidget {
  const RoomsScreen({super.key});

  @override
  State<RoomsScreen> createState() => _RoomsScreenState();
}

class _RoomsScreenState extends State<RoomsScreen> {
  bool _isLoading = true;
  String? _errorMessage;

  String _selectedRoom = 'A'; // 'A' | 'B' | 'C'
  List<dynamic> _allSeats = [];
  Map<String, List<dynamic>> _groupedOccupants = {};

  // Room layout stats
  int _rows = 5;
  int _columns = 5;

  @override
  void initState() {
    super.initState();
    _loadRoomData();
  }

  Future<void> _loadRoomData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      // 1. Fetch layout size for target room
      final layout = await ApiService.getRoomLayout(_selectedRoom);
      
      // 2. Fetch all seats
      final seatsData = await ApiService.getAllSeats();

      // 3. Fetch all active students to group them by seat
      final studentsData = await ApiService.getStudents(filter: "Active");

      // Group active students by seat number
      final Map<String, List<dynamic>> grouped = {};
      for (var student in studentsData) {
        final seat = student['seat_number'] as String?;
        if (seat != null) {
          grouped.putIfAbsent(seat, () => []).add(student);
        }
      }

      setState(() {
        _rows = layout['rows'] ?? 5;
        _columns = layout['columns'] ?? 5;
        _allSeats = seatsData;
        _groupedOccupants = grouped;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _isLoading = false;
      });
    }
  }

  // Get seats belonging to current selected room
  List<dynamic> _getFilteredSeats() {
    final list = _allSeats.where((seat) {
      final r = seat['room'] ?? 'A';
      return r.toString().trim().toUpperCase() == _selectedRoom;
    }).toList();
    // Sort alphabetically by seat number
    list.sort((a, b) => (a['seat_number'] ?? '').toString().compareTo((b['seat_number'] ?? '').toString()));
    return list;
  }

  Color _getSeatColor(List<dynamic> occupants) {
    if (occupants.isEmpty) {
      return AppColors.success; // Available (Green)
    }

    final shifts = occupants.map((s) => s['shift_type'] ?? 'FULL_DAY').toList();

    if (shifts.contains('FULL_DAY')) {
      return AppColors.danger; // Occupied Full Day (Red)
    }

    if (occupants.length == 2) {
      return const Color(0xFF2563EB); // Shared both slots filled (Blue)
    }

    // Exactly 1 half day student
    return AppColors.warning; // Shared partial (Yellow/Amber)
  }

  String _getSeatShiftShortLabel(List<dynamic> occupants) {
    if (occupants.isEmpty) return 'Avail';
    final shifts = occupants.map((s) => s['shift_type'] ?? 'FULL_DAY').toList();
    if (shifts.contains('FULL_DAY')) return 'Full';
    if (occupants.length == 2) return 'Shared';
    
    // Exactly 1
    if (shifts.first == 'HALF_DAY_DAY') return 'Day';
    return 'Night';
  }

  @override
  Widget build(BuildContext context) {
    final filteredSeats = _getFilteredSeats();

    return Scaffold(
      appBar: AppBar(
        title: const Text('🗺️ Room Seats Layout'),
      ),
      body: Column(
        children: [
          _buildRoomSelector(),
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator(color: AppColors.accent))
                : _errorMessage != null
                    ? _buildErrorView()
                    : filteredSeats.isEmpty
                        ? _buildEmptyView()
                        : Column(
                            children: [
                              _buildLayoutInfoSummary(),
                              Expanded(
                                child: RefreshIndicator(
                                  onRefresh: _loadRoomData,
                                  child: GridView.builder(
                                    padding: const EdgeInsets.all(16),
                                    gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                                      crossAxisCount: _columns > 0 ? _columns : 5,
                                      crossAxisSpacing: 10.0,
                                      mainAxisSpacing: 10.0,
                                      childAspectRatio: 1.0,
                                    ),
                                    itemCount: filteredSeats.length,
                                    itemBuilder: (context, idx) {
                                      final seat = filteredSeats[idx];
                                      final seatNumber = seat['seat_number'] ?? '';
                                      final occupants = _groupedOccupants[seatNumber] ?? [];
                                      final seatColor = _getSeatColor(occupants);
                                      final shortLabel = _getSeatShiftShortLabel(occupants);

                                      return _buildSeatTile(seatNumber, occupants, seatColor, shortLabel);
                                    },
                                  ),
                                ),
                              ),
                              _buildColorLegend(),
                            ],
                          ),
          ),
        ],
      ),
    );
  }

  Widget _buildRoomSelector() {
    return Container(
      color: AppColors.primary,
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: ['A', 'B', 'C'].map((room) {
          final isSelected = _selectedRoom == room;
          return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 6.0),
            child: ChoiceChip(
              label: Text(
                'Room $room',
                style: TextStyle(
                  color: isSelected ? Colors.white : AppColors.textSecondary,
                  fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                ),
              ),
              selected: isSelected,
              selectedColor: AppColors.accent,
              backgroundColor: AppColors.primary.withAlpha(50),
              checkmarkColor: Colors.white,
              side: BorderSide.none,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
              onSelected: (selected) {
                if (selected) {
                  setState(() {
                    _selectedRoom = room;
                  });
                  _loadRoomData();
                }
              },
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildLayoutInfoSummary() {
    final filteredSeatsCount = _getFilteredSeats().length;
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
      color: AppColors.bg,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            'Total Seats: $filteredSeatsCount',
            style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 13),
          ),
          Text(
            'Grid dimensions: $_rows × $_columns',
            style: const TextStyle(color: AppColors.textSecondary, fontSize: 12),
          ),
        ],
      ),
    );
  }

  Widget _buildSeatTile(String seatNumber, List<dynamic> occupants, Color color, String shortLabel) {
    return InkWell(
      onTap: () => _handleSeatClick(seatNumber, occupants),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        decoration: BoxDecoration(
          color: color.withOpacity(0.08),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withOpacity(0.6), width: 1.5),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              seatNumber,
              style: TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 15,
                color: color == AppColors.success ? AppColors.textPrimary : color,
              ),
            ),
            const SizedBox(height: 2),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
              decoration: BoxDecoration(
                color: color.withOpacity(0.12),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                shortLabel,
                style: TextStyle(
                  fontSize: 9,
                  fontWeight: FontWeight.w600,
                  color: color == AppColors.success ? AppColors.textSecondary : color,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _handleSeatClick(String seatNumber, List<dynamic> occupants) {
    if (occupants.isEmpty) {
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text('Seat $seatNumber is Empty'),
          content: const Text('This seat is currently available for allocation. Would you like to admit a new student to this seat?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel', style: TextStyle(color: AppColors.textSecondary)),
            ),
            ElevatedButton(
              onPressed: () async {
                Navigator.pop(ctx);
                final result = await Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => const StudentFormScreen(), // Will open form
                  ),
                );
                if (result == true) {
                  _loadRoomData();
                }
              },
              style: ElevatedButton.styleFrom(backgroundColor: AppColors.accent, foregroundColor: Colors.white),
              child: const Text('New Admission'),
            ),
          ],
        ),
      );
    } else {
      _showOccupantDetailsSheet(seatNumber, occupants);
    }
  }

  void _showOccupantDetailsSheet(String seatNumber, List<dynamic> occupants) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return Container(
          padding: const EdgeInsets.all(20.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Seat $seatNumber Occupancy',
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppColors.primary.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      '${occupants.length} Active Student(s)',
                      style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppColors.primary),
                    ),
                  ),
                ],
              ),
              const Divider(height: 24),
              Flexible(
                child: ListView.builder(
                  shrinkWrap: true,
                  itemCount: occupants.length,
                  itemBuilder: (lCtx, idx) {
                    final student = occupants[idx];
                    final String name = student['full_name'] ?? '';
                    final String shift = student['shift_type'] ?? 'FULL_DAY';
                    final String mobile = student['mobile_number'] ?? '';
                    final int studentId = student['id'];

                    return Card(
                      margin: const EdgeInsets.symmetric(vertical: 6),
                      child: ListTile(
                        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                        title: Text(name, style: const TextStyle(fontWeight: FontWeight.bold)),
                        subtitle: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const SizedBox(height: 4),
                            Text('Shift: $shift', style: const TextStyle(fontSize: 12)),
                            Text('Mobile: $mobile', style: const TextStyle(fontSize: 12)),
                          ],
                        ),
                        trailing: OutlinedButton(
                          onPressed: () async {
                            Navigator.pop(ctx); // Close sheet
                            final result = await Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (context) => StudentDetailScreen(studentId: studentId),
                              ),
                            );
                            if (result == true) {
                              _loadRoomData();
                            }
                          },
                          style: OutlinedButton.styleFrom(
                            foregroundColor: AppColors.accent,
                            side: const BorderSide(color: AppColors.accent),
                          ),
                          child: const Text('View Profile'),
                        ),
                      ),
                    );
                  },
                ),
              ),
              const SizedBox(height: 12),
            ],
          ),
        );
      },
    );
  }

  Widget _buildColorLegend() {
    return Container(
      decoration: const BoxDecoration(
        color: AppColors.cardBg,
        border: Border(top: BorderSide(color: AppColors.border)),
      ),
      padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildLegendItem(AppColors.success, 'Available'),
              _buildLegendItem(AppColors.danger, 'Occupied (Full Day)'),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildLegendItem(AppColors.warning, 'Shared (Open Slot)'),
              _buildLegendItem(const Color(0xFF2563EB), 'Shared (Both Slots)'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildLegendItem(Color color, String label) {
    return Row(
      children: [
        Container(
          width: 14,
          height: 14,
          decoration: BoxDecoration(
            color: color.withOpacity(0.1),
            borderRadius: BorderRadius.circular(4),
            border: Border.all(color: color, width: 1.5),
          ),
        ),
        const SizedBox(width: 8),
        Text(
          label,
          style: const TextStyle(fontSize: 12, color: AppColors.textSecondary, fontWeight: FontWeight.w500),
        ),
      ],
    );
  }

  Widget _buildEmptyView() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.chair_alt_rounded, color: AppColors.textSecondary, size: 64),
          SizedBox(height: 16),
          Text(
            'No seats registered for this room layout.',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorView() {
    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline_rounded, color: AppColors.danger, size: 64),
            const SizedBox(height: 16),
            const Text(
              'Error loading room grid',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
            ),
            const SizedBox(height: 8),
            Text(
              _errorMessage ?? 'Unknown error',
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.textSecondary),
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: _loadRoomData,
              style: ElevatedButton.styleFrom(backgroundColor: AppColors.accent, foregroundColor: Colors.white),
              child: const Text('Reload'),
            ),
          ],
        ),
      ),
    );
  }
}
