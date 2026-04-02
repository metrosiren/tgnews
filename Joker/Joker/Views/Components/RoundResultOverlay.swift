import SwiftUI

// MARK: - Round result overlay

struct RoundResultOverlay: View {
    let result: RoundResult
    let onPlayAgain: () -> Void

    @State private var appeared = false

    var body: some View {
        ZStack {
            Color.black.opacity(0.68).ignoresSafeArea()
                .transition(.opacity)

            VStack(spacing: 26) {
                Text(result.emoji)
                    .font(.system(size: 72))
                    .scaleEffect(appeared ? 1.0 : 0.2)
                    .animation(.spring(response: 0.4, dampingFraction: 0.5), value: appeared)

                VStack(spacing: 8) {
                    Text(result.title)
                        .font(.system(size: 38, weight: .black, design: .rounded))
                        .foregroundColor(result.titleColor)

                    Text(result.subtitle)
                        .font(.system(size: 16, weight: .semibold, design: .rounded))
                        .foregroundColor(.white.opacity(0.7))
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 8)
                }
                .opacity(appeared ? 1 : 0)
                .animation(.easeIn(duration: 0.3).delay(0.2), value: appeared)

                Button(action: onPlayAgain) {
                    Text("PLAY AGAIN")
                        .font(.system(size: 20, weight: .black, design: .rounded))
                        .foregroundColor(.black)
                        .padding(.horizontal, 44)
                        .padding(.vertical, 16)
                        .background(
                            Capsule()
                                .fill(result.titleColor)
                                .overlay(Capsule().stroke(Color.black, lineWidth: 2.5))
                        )
                }
                .scaleEffect(appeared ? 1.0 : 0.8)
                .animation(.spring(response: 0.3, dampingFraction: 0.65).delay(0.4),
                           value: appeared)
            }
            .padding(32)
        }
        .onAppear { appeared = true }
        .onDisappear { appeared = false }
    }
}

// MARK: - RoundResult display helpers

extension RoundResult {
    var emoji: String {
        switch self {
        case .playerWins: return "🏆"
        case .dealerWins: return "😤"
        case .push:       return "🤝"
        case .playerBust: return "💥"
        case .dealerBust: return "🎉"
        }
    }

    var title: String {
        switch self {
        case .playerWins: return "YOU WIN!"
        case .dealerWins: return "DEALER WINS"
        case .push:       return "PUSH"
        case .playerBust: return "BUST!"
        case .dealerBust: return "DEALER BUST!"
        }
    }

    var subtitle: String {
        switch self {
        case .playerWins: return "Closer to 21 – well played!"
        case .dealerWins: return "Dealer had the better hand."
        case .push:       return "It's a tie – bets returned."
        case .playerBust: return "Over 21 – too many cards!"
        case .dealerBust: return "Dealer went over 21. You win!"
        }
    }

    var titleColor: Color {
        switch self {
        case .playerWins, .dealerBust: return .unoGreen
        case .dealerWins, .playerBust: return .unoRed
        case .push:                    return .unoYellow
        }
    }
}
