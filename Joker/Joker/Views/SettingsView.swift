import SwiftUI

struct SettingsView: View {

    @AppStorage("difficulty")      private var difficultyRaw: String = Difficulty.normal.rawValue
    @AppStorage("soundEnabled")    private var soundEnabled: Bool    = true
    @AppStorage("hapticsEnabled")  private var hapticsEnabled: Bool  = true

    private var difficulty: Binding<Difficulty> {
        Binding(
            get: { Difficulty(rawValue: difficultyRaw) ?? .normal },
            set: { difficultyRaw = $0.rawValue }
        )
    }

    var body: some View {
        ZStack {
            Color.feltDark.ignoresSafeArea()

            List {

                // GAME
                Section {
                    difficultyPicker
                } header: { sectionHeader("GAME") }

                // FEEDBACK
                Section {
                    Toggle("Sound Effects", isOn: $soundEnabled)
                        .tint(.unoGreen)
                        .foregroundColor(.white)
                        .listRowBackground(rowBackground)

                    Toggle("Haptic Feedback", isOn: $hapticsEnabled)
                        .tint(.unoBlue)
                        .foregroundColor(.white)
                        .listRowBackground(rowBackground)
                } header: { sectionHeader("FEEDBACK") }

                // ABOUT
                Section {
                    HStack {
                        Text("Version")
                            .foregroundColor(.white)
                        Spacer()
                        Text("1.0.0")
                            .foregroundColor(.white.opacity(0.45))
                    }
                    .listRowBackground(rowBackground)
                } header: { sectionHeader("ABOUT") }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Settings")
        .navigationBarTitleDisplayMode(.large)
    }

    // MARK: - Difficulty segment picker

    private var difficultyPicker: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Difficulty")
                .font(.system(size: 15, weight: .semibold, design: .rounded))
                .foregroundColor(.white)

            HStack(spacing: 0) {
                ForEach(Difficulty.allCases, id: \.self) { d in
                    Button { difficulty.wrappedValue = d } label: {
                        Text(d.rawValue)
                            .font(.system(size: 14, weight: .black, design: .rounded))
                            .foregroundColor(difficulty.wrappedValue == d ? .black : .white.opacity(0.55))
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 10)
                            .background(
                                RoundedRectangle(cornerRadius: 10)
                                    .fill(difficulty.wrappedValue == d
                                          ? segmentColor(d)
                                          : Color.clear)
                            )
                            .animation(.easeInOut(duration: 0.15), value: difficulty.wrappedValue)
                    }
                }
            }
            .padding(4)
            .background(
                RoundedRectangle(cornerRadius: 14)
                    .fill(Color.white.opacity(0.10))
            )
        }
        .listRowBackground(rowBackground)
    }

    private func segmentColor(_ d: Difficulty) -> Color {
        switch d {
        case .easy:   return .unoGreen
        case .normal: return .unoYellow
        case .hard:   return .unoRed
        }
    }

    // MARK: - Helpers

    private var rowBackground: some View {
        Color.white.opacity(0.06)
    }

    private func sectionHeader(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11, weight: .bold, design: .rounded))
            .foregroundColor(.white.opacity(0.4))
            .tracking(2)
    }
}
