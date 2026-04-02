import SwiftUI

struct HomeView: View {

    @State private var logoScale: CGFloat = 0.4
    @State private var logoRotation: Double = -18
    @State private var showButtons = false

    var body: some View {
        NavigationStack {
            ZStack {
                // Background felt
                Color.feltDark.ignoresSafeArea()
                RadialGradient(
                    colors: [Color.feltGreen.opacity(0.55), Color.clear],
                    center: .center,
                    startRadius: 60,
                    endRadius: 380
                )
                .ignoresSafeArea()

                VStack(spacing: 0) {
                    Spacer()

                    // Animated logo stack
                    logoStack
                        .padding(.bottom, 28)

                    // Title
                    VStack(spacing: 6) {
                        Text("JOKER")
                            .font(.system(size: 54, weight: .black, design: .rounded))
                            .foregroundStyle(
                                LinearGradient(
                                    colors: [.jokerGold, .yellow, .jokerGold],
                                    startPoint: .leading,
                                    endPoint: .trailing
                                )
                            )
                            .shadow(color: .black.opacity(0.7), radius: 3, x: 2, y: 3)

                        Text("Blackjack  ×  Uno")
                            .font(.system(size: 18, weight: .semibold, design: .rounded))
                            .foregroundColor(.white.opacity(0.65))
                            .tracking(1)
                    }
                    .opacity(showButtons ? 1 : 0)
                    .animation(.easeIn(duration: 0.45).delay(0.25), value: showButtons)

                    Spacer()

                    // Navigation buttons
                    if showButtons {
                        VStack(spacing: 14) {
                            NavigationLink(destination: GameView()) {
                                MenuButton(title: "PLAY",     color: .unoRed,   icon: "play.fill")
                            }
                            NavigationLink(destination: RulesView()) {
                                MenuButton(title: "RULES",    color: .unoBlue,  icon: "book.fill")
                            }
                            NavigationLink(destination: SettingsView()) {
                                MenuButton(title: "SETTINGS", color: .unoGreen, icon: "gearshape.fill")
                            }
                        }
                        .padding(.horizontal, 36)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                    }

                    Spacer().frame(height: 48)
                }
            }
            .onAppear {
                withAnimation(.spring(response: 0.6, dampingFraction: 0.58).delay(0.15)) {
                    logoScale    = 1.0
                    logoRotation = 0
                }
                withAnimation(.easeOut(duration: 0.4).delay(0.55)) {
                    showButtons = true
                }
            }
        }
    }

    // MARK: - Logo

    private var logoStack: some View {
        ZStack {
            // Fanned background cards
            ForEach(0 ..< 3) { i in
                RoundedRectangle(cornerRadius: 18)
                    .fill(Color.white)
                    .frame(width: 126, height: 180)
                    .overlay(
                        RoundedRectangle(cornerRadius: 18)
                            .stroke(Color.black, lineWidth: 3)
                    )
                    .rotationEffect(.degrees(Double(i - 1) * 13))
                    .shadow(color: .black.opacity(0.35), radius: 6, x: 0, y: 4)
            }

            // Top joker card
            RoundedRectangle(cornerRadius: 18)
                .fill(
                    LinearGradient(
                        colors: [.unoRed, .unoBlue],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .frame(width: 126, height: 180)
                .overlay(
                    RoundedRectangle(cornerRadius: 18)
                        .stroke(Color.jokerGold, lineWidth: 4)
                )
                .overlay(
                    VStack(spacing: 5) {
                        Text("🃏").font(.system(size: 60))
                        Text("JOKER")
                            .font(.system(size: 14, weight: .black, design: .rounded))
                            .foregroundColor(.jokerGold)
                    }
                )
                .shadow(color: Color.jokerGold.opacity(0.55), radius: 16)
        }
        .scaleEffect(logoScale)
        .rotationEffect(.degrees(logoRotation))
    }
}

// MARK: - Menu button

struct MenuButton: View {
    let title: String
    let color: Color
    let icon: String

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: icon)
                .font(.system(size: 18, weight: .bold))
            Text(title)
                .font(.system(size: 20, weight: .black, design: .rounded))
            Spacer()
            Image(systemName: "chevron.right")
                .font(.system(size: 14, weight: .bold))
                .opacity(0.7)
        }
        .foregroundColor(.white)
        .padding(.horizontal, 22)
        .padding(.vertical, 16)
        .background(
            RoundedRectangle(cornerRadius: 18)
                .fill(color)
                .overlay(
                    RoundedRectangle(cornerRadius: 18)
                        .stroke(Color.black, lineWidth: 3)
                )
        )
        .shadow(color: color.opacity(0.5), radius: 8, x: 0, y: 4)
    }
}
