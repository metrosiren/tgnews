import SwiftUI

// MARK: - CardView

struct CardView: View {
    let card: Card
    var isSelected: Bool = false
    var faceDown: Bool   = false

    var body: some View {
        ZStack {
            if faceDown || !card.isFaceUp {
                cardBack
            } else {
                cardFront
            }
        }
        .frame(width: 72, height: 104)
        .shadow(
            color: isSelected ? Color.jokerGold.opacity(0.7) : Color.black.opacity(0.4),
            radius: isSelected ? 12 : 4,
            x: 0,
            y: isSelected ? 8 : 3
        )
        .scaleEffect(isSelected ? 1.08 : 1.0)
        .animation(.spring(response: 0.28, dampingFraction: 0.65), value: isSelected)
    }

    // MARK: Card back

    private var cardBack: some View {
        RoundedRectangle(cornerRadius: 12)
            .fill(
                LinearGradient(
                    colors: [Color(red: 0.10, green: 0.08, blue: 0.50),
                             Color(red: 0.28, green: 0.00, blue: 0.50)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.white.opacity(0.25), lineWidth: 3)
            )
            .overlay(
                Image(systemName: "suit.diamond.fill")
                    .font(.system(size: 26, weight: .bold))
                    .foregroundColor(.white.opacity(0.4))
            )
    }

    // MARK: Card front

    private var cardFront: some View {
        RoundedRectangle(cornerRadius: 12)
            .fill(Color.white)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.black, lineWidth: 3)
            )
            .overlay(cardContent)
    }

    @ViewBuilder
    private var cardContent: some View {
        switch card.type {
        case .number(let n):
            NumberCardFace(number: n, color: Color.cardColor(for: card.color))
        case .joker:
            JokerCardFace()
        default:
            ActionCardFace(
                label: card.type.displayName,
                symbol: card.type.symbolText,
                color: Color.cardColor(for: card.color)
            )
        }
    }
}

// MARK: - Number card face

private struct NumberCardFace: View {
    let number: Int
    let color: Color

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 9)
                .fill(color)
                .padding(5)

            VStack(spacing: 0) {
                cornerLabel(String(number), alignment: .leading)
                Spacer()
                Text(String(number))
                    .font(.system(size: 30, weight: .black, design: .rounded))
                    .foregroundColor(.white)
                Spacer()
                cornerLabel(String(number), alignment: .trailing)
                    .rotationEffect(.degrees(180))
            }
            .padding(6)
        }
        .padding(4)
    }

    private func cornerLabel(_ text: String, alignment: Alignment) -> some View {
        Text(text)
            .font(.system(size: 13, weight: .black, design: .rounded))
            .foregroundColor(.white)
            .frame(maxWidth: .infinity, alignment: alignment)
    }
}

// MARK: - Action card face

private struct ActionCardFace: View {
    let label: String
    let symbol: String
    let color: Color

    var body: some View {
        ZStack {
            Ellipse()
                .fill(color)
                .padding(.horizontal, 6)
                .padding(.vertical, 3)

            VStack(spacing: 0) {
                Text(label)
                    .font(.system(size: 8, weight: .black, design: .rounded))
                    .foregroundColor(color)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.leading, 5)
                    .padding(.top, 5)

                Spacer()

                Text(symbol)
                    .font(.system(size: 22, weight: .black, design: .rounded))
                    .foregroundColor(.white)

                Spacer()

                Text(label)
                    .font(.system(size: 8, weight: .black, design: .rounded))
                    .foregroundColor(color)
                    .frame(maxWidth: .infinity, alignment: .trailing)
                    .padding(.trailing, 5)
                    .padding(.bottom, 5)
                    .rotationEffect(.degrees(180))
            }
        }
        .padding(4)
    }
}

// MARK: - Joker card face

private struct JokerCardFace: View {
    var body: some View {
        ZStack {
            LinearGradient(
                colors: [.unoRed, .unoBlue, .unoGreen, .unoYellow],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .clipShape(RoundedRectangle(cornerRadius: 9))
            .padding(5)

            VStack(spacing: 2) {
                Text("J")
                    .font(.system(size: 11, weight: .black, design: .rounded))
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.leading, 7)
                    .padding(.top, 5)

                Spacer()
                Text("🃏").font(.system(size: 28))
                Text("JOKER")
                    .font(.system(size: 8, weight: .black, design: .rounded))
                    .foregroundColor(.jokerGold)
                Spacer()

                Text("J")
                    .font(.system(size: 11, weight: .black, design: .rounded))
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity, alignment: .trailing)
                    .padding(.trailing, 7)
                    .padding(.bottom, 5)
                    .rotationEffect(.degrees(180))
            }
        }
        .padding(4)
    }
}
