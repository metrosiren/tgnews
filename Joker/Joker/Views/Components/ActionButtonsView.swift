import SwiftUI

// MARK: - Primary action button (HIT / STAND / PLAY)

struct ActionButton: View {
    let title: String
    let color: Color
    let icon: String
    let isEnabled: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 5) {
                Image(systemName: icon)
                    .font(.system(size: 22, weight: .bold))
                Text(title)
                    .font(.system(size: 13, weight: .black, design: .rounded))
            }
            .foregroundColor(isEnabled ? .white : .white.opacity(0.3))
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(
                RoundedRectangle(cornerRadius: 16)
                    .fill(isEnabled ? color : Color.gray.opacity(0.25))
                    .overlay(
                        RoundedRectangle(cornerRadius: 16)
                            .stroke(isEnabled ? Color.black : Color.clear, lineWidth: 2.5)
                    )
            )
            .shadow(
                color: isEnabled ? color.opacity(0.45) : .clear,
                radius: 6, x: 0, y: 4
            )
        }
        .disabled(!isEnabled)
        .animation(.easeInOut(duration: 0.15), value: isEnabled)
    }
}

// MARK: - Small stat badge (W / L / P)

struct StatBadge: View {
    let label: String
    let value: Int
    let color: Color

    var body: some View {
        VStack(spacing: 1) {
            Text(label)
                .font(.system(size: 9, weight: .bold, design: .rounded))
                .foregroundColor(color)
            Text("\(value)")
                .font(.system(size: 17, weight: .black, design: .rounded))
                .foregroundColor(.white)
        }
        .frame(minWidth: 28)
    }
}
