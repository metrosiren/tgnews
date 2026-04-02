import SwiftUI

// MARK: - Uno / game theme colours

extension Color {
    static let unoRed    = Color(red: 0.94, green: 0.16, blue: 0.12)
    static let unoBlue   = Color(red: 0.06, green: 0.37, blue: 0.82)
    static let unoGreen  = Color(red: 0.06, green: 0.63, blue: 0.20)
    static let unoYellow = Color(red: 1.00, green: 0.80, blue: 0.00)

    static let feltDark  = Color(red: 0.04, green: 0.16, blue: 0.07)
    static let feltGreen = Color(red: 0.08, green: 0.28, blue: 0.12)
    static let jokerGold = Color(red: 1.00, green: 0.75, blue: 0.00)

    /// Map a `CardColor` (or nil for colourless cards) to its display colour.
    static func cardColor(for color: CardColor?) -> Color {
        switch color {
        case .red:    return .unoRed
        case .blue:   return .unoBlue
        case .green:  return .unoGreen
        case .yellow: return .unoYellow
        case nil:     return Color(red: 0.15, green: 0.15, blue: 0.15)
        }
    }
}
