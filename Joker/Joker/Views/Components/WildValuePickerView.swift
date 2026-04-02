import SwiftUI

/// Modal sheet that lets the player choose a value for a Wild or Joker card.
/// For Joker cards the player also selects a dealer effect.
struct WildValuePickerView: View {
    let isJokerSpecial: Bool
    let onConfirm: (Int, DealerEffect?) -> Void

    @State private var selectedValue: Int         = 5
    @State private var selectedEffect: DealerEffect? = nil

    private let values = Array(1 ... 10)

    private var canConfirm: Bool {
        !isJokerSpecial || selectedEffect != nil
    }

    var body: some View {
        ZStack {
            Color.black.opacity(0.72).ignoresSafeArea()

            VStack(spacing: 22) {

                // Header
                Text(isJokerSpecial ? "🃏  JOKER" : "★  WILD")
                    .font(.system(size: 30, weight: .black, design: .rounded))
                    .foregroundStyle(
                        isJokerSpecial
                            ? LinearGradient(
                                colors: [.unoRed, .unoBlue, .unoGreen, .unoYellow],
                                startPoint: .leading, endPoint: .trailing)
                            : LinearGradient(
                                colors: [.white, .white],
                                startPoint: .leading, endPoint: .trailing)
                    )

                Text("Choose card value")
                    .font(.system(size: 15, weight: .semibold, design: .rounded))
                    .foregroundColor(.white.opacity(0.65))

                // Value grid
                LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 5),
                          spacing: 10) {
                    ForEach(values, id: \.self) { v in
                        Button { selectedValue = v } label: {
                            Text("\(v)")
                                .font(.system(size: 20, weight: .black, design: .rounded))
                                .frame(width: 46, height: 46)
                                .background(
                                    Circle()
                                        .fill(selectedValue == v ? Color.unoYellow : Color.white.opacity(0.12))
                                )
                                .foregroundColor(selectedValue == v ? .black : .white)
                        }
                    }
                }

                // Joker effect picker
                if isJokerSpecial {
                    Divider().background(Color.white.opacity(0.25))

                    Text("Choose dealer action")
                        .font(.system(size: 14, weight: .semibold, design: .rounded))
                        .foregroundColor(.white.opacity(0.65))

                    HStack(spacing: 10) {
                        effectButton(.skipNextDraw, label: "Skip",    icon: "slash.circle.fill")
                        effectButton(.discardCard,  label: "Discard", icon: "trash.fill")
                        effectButton(.drawExtra(2), label: "+2",      icon: "plus.circle.fill")
                        effectButton(.drawExtra(4), label: "+4",      icon: "plus.square.fill")
                    }
                }

                // Confirm
                Button {
                    onConfirm(selectedValue, isJokerSpecial ? selectedEffect : nil)
                } label: {
                    Text("CONFIRM")
                        .font(.system(size: 18, weight: .black, design: .rounded))
                        .foregroundColor(.black)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(
                            RoundedRectangle(cornerRadius: 16)
                                .fill(canConfirm ? Color.jokerGold : Color.gray.opacity(0.4))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 16)
                                        .stroke(Color.black, lineWidth: 2.5)
                                )
                        )
                }
                .disabled(!canConfirm)
                .opacity(canConfirm ? 1.0 : 0.5)
            }
            .padding(26)
            .background(
                RoundedRectangle(cornerRadius: 24)
                    .fill(Color(red: 0.08, green: 0.08, blue: 0.14))
                    .overlay(
                        RoundedRectangle(cornerRadius: 24)
                            .stroke(Color.jokerGold, lineWidth: 2)
                    )
            )
            .padding(.horizontal, 20)
        }
    }

    private func effectButton(_ effect: DealerEffect, label: String, icon: String) -> some View {
        let active = selectedEffect == effect
        return Button { selectedEffect = effect } label: {
            VStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.system(size: 20, weight: .bold))
                Text(label)
                    .font(.system(size: 11, weight: .bold, design: .rounded))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(active ? Color.jokerGold : Color.white.opacity(0.10))
            )
            .foregroundColor(active ? .black : .white)
            .animation(.easeInOut(duration: 0.12), value: active)
        }
    }
}
