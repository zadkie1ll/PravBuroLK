import { createTheme } from "@mui/material/styles";

export const educationTheme = createTheme({
  palette: {
    primary: { main: "#333333", contrastText: "#ffffff" },
    background: { default: "#f3f4f6", paper: "#ffffff" },
    text: { primary: "#333333", secondary: "#6b7280" },
    divider: "#e5e7eb",
  },
  typography: { fontFamily: 'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', button: { textTransform: "none", fontWeight: 600 } },
  shape: { borderRadius: 12 },
  components: {
    MuiButton: { defaultProps: { disableElevation: true }, styleOverrides: { root: { borderRadius: 8 } } },
    MuiPaper: { styleOverrides: { root: { backgroundImage: "none", boxShadow: "none", border: "1px solid #e5e7eb" } } },
    MuiAccordion: { defaultProps: { disableGutters: true }, styleOverrides: { root: { borderRadius: "12px !important", marginBottom: 16, "&:before": { display: "none" } } } },
    MuiDialog: { styleOverrides: { paper: { borderRadius: 16 } } },
    MuiChip: { styleOverrides: { root: { backgroundColor: "#eef2f6", color: "#475569" } } },
    MuiTextField: { defaultProps: { size: "small" } },
    MuiTableCell: { styleOverrides: { head: { backgroundColor: "#f8fafc", fontWeight: 600 }, root: { borderColor: "#e5e7eb" } } },
  },
});
