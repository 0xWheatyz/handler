/* @ds-bundle: {"format":4,"namespace":"LeeworksDesignSystem_b3e560","components":[{"name":"Badge","sourcePath":"components/display/Badge.jsx"},{"name":"Card","sourcePath":"components/display/Card.jsx"},{"name":"Icon","sourcePath":"components/display/Icon.jsx"},{"name":"Tag","sourcePath":"components/display/Tag.jsx"},{"name":"Dialog","sourcePath":"components/feedback/Dialog.jsx"},{"name":"Toast","sourcePath":"components/feedback/Toast.jsx"},{"name":"Tooltip","sourcePath":"components/feedback/Tooltip.jsx"},{"name":"Button","sourcePath":"components/forms/Button.jsx"},{"name":"Checkbox","sourcePath":"components/forms/Checkbox.jsx"},{"name":"IconButton","sourcePath":"components/forms/IconButton.jsx"},{"name":"Input","sourcePath":"components/forms/Input.jsx"},{"name":"Radio","sourcePath":"components/forms/Radio.jsx"},{"name":"Select","sourcePath":"components/forms/Select.jsx"},{"name":"Switch","sourcePath":"components/forms/Switch.jsx"},{"name":"Tabs","sourcePath":"components/navigation/Tabs.jsx"}],"sourceHashes":{"components/display/Badge.jsx":"8997328a4111","components/display/Card.jsx":"ab40881f63ba","components/display/Icon.jsx":"81142bbf0632","components/display/Tag.jsx":"0246746ae4e7","components/feedback/Dialog.jsx":"46659251cb35","components/feedback/Toast.jsx":"de88ee2df7f1","components/feedback/Tooltip.jsx":"5aa98d55e4d0","components/forms/Button.jsx":"93685df3a1e6","components/forms/Checkbox.jsx":"5ee3266eec63","components/forms/IconButton.jsx":"3ac35be6b500","components/forms/Input.jsx":"e4c070c9f68d","components/forms/Radio.jsx":"e89340749f32","components/forms/Select.jsx":"2a886e5c15d0","components/forms/Switch.jsx":"27342bd5bd50","components/navigation/Tabs.jsx":"4f25ba202346","ui_kits/dashboard/Overview.jsx":"0099fff42ce5","ui_kits/dashboard/Reports.jsx":"5c8b3c989412","ui_kits/dashboard/SettingsScreen.jsx":"33bba4658f06","ui_kits/dashboard/Shell.jsx":"ec2cfc201f23","ui_kits/mobile/MHome.jsx":"2be7b70c7365","ui_kits/mobile/MInbox.jsx":"4b6c4c0a1840","ui_kits/mobile/MProfile.jsx":"caa0d4bc691e","ui_kits/mobile/MobileShell.jsx":"7fe720ae45f4","ui_kits/website/Features.jsx":"7a70ffe310b0","ui_kits/website/Hero.jsx":"beac30775690","ui_kits/website/SiteFooter.jsx":"61be12284b8e","ui_kits/website/SiteNav.jsx":"122448ae9f26"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.LeeworksDesignSystem_b3e560 = window.LeeworksDesignSystem_b3e560 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/display/Badge.jsx
try { (() => {
function Badge({
  tone = "neutral",
  children,
  style
}) {
  const tones = {
    neutral: {
      background: "var(--ink-1)",
      color: "var(--ink-7)"
    },
    positive: {
      background: "var(--positive-tint)",
      color: "var(--positive)"
    },
    warning: {
      background: "var(--warning-tint)",
      color: "var(--warning)"
    },
    danger: {
      background: "var(--danger-tint)",
      color: "var(--danger)"
    },
    inverse: {
      background: "var(--surface-inverse)",
      color: "var(--text-inverse)"
    }
  };
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: "6px",
      padding: "3px 10px",
      borderRadius: "var(--radius-pill)",
      font: "var(--type-caption)",
      fontWeight: 600,
      whiteSpace: "nowrap",
      ...tones[tone],
      ...style
    }
  }, children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/display/Badge.jsx", error: String((e && e.message) || e) }); }

// components/display/Card.jsx
try { (() => {
function Card({
  title,
  subtitle,
  actions = null,
  footer = null,
  variant = "default",
  padding = "var(--space-6)",
  children,
  style
}) {
  const variants = {
    default: {
      background: "var(--surface-card)",
      border: "1px solid var(--border-subtle)",
      boxShadow: "var(--shadow-card)"
    },
    sunken: {
      background: "var(--surface-sunken)",
      border: "none",
      boxShadow: "none"
    },
    outline: {
      background: "var(--surface-card)",
      border: "1px solid var(--border-default)",
      boxShadow: "none"
    }
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      borderRadius: "var(--radius-lg)",
      display: "flex",
      flexDirection: "column",
      ...variants[variant],
      ...style
    }
  }, (title || actions) && /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: "12px",
      padding: `${padding} ${padding} 0`
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, title && /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-h4)",
      color: "var(--text-heading)",
      fontFamily: "var(--font-display)"
    }
  }, title), subtitle && /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-body-sm)",
      color: "var(--text-muted)",
      marginTop: "2px"
    }
  }, subtitle)), actions), /*#__PURE__*/React.createElement("div", {
    style: {
      padding,
      flex: 1
    }
  }, children), footer && /*#__PURE__*/React.createElement("div", {
    style: {
      borderTop: "1px solid var(--border-subtle)",
      padding: `var(--space-3) ${padding}`,
      font: "var(--type-body-sm)",
      color: "var(--text-muted)"
    }
  }, footer));
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/display/Card.jsx", error: String((e && e.message) || e) }); }

// components/display/Icon.jsx
try { (() => {
// Lucide icon paths (lucide.dev, ISC) inlined for React use — 1.75 stroke, currentColor.
const P = {
  dashboard: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("rect", {
    x: "3",
    y: "3",
    width: "7",
    height: "9",
    rx: "1"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "14",
    y: "3",
    width: "7",
    height: "5",
    rx: "1"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "14",
    y: "12",
    width: "7",
    height: "9",
    rx: "1"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "3",
    y: "16",
    width: "7",
    height: "5",
    rx: "1"
  })),
  file: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M14 2v4a2 2 0 0 0 2 2h4"
  })),
  users: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "9",
    cy: "7",
    r: "4"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M22 21v-2a4 4 0 0 0-3-3.87"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M16 3.13a4 4 0 0 1 0 7.75"
  })),
  settings: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "12",
    cy: "12",
    r: "3"
  })),
  search: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("circle", {
    cx: "11",
    cy: "11",
    r: "8"
  }), /*#__PURE__*/React.createElement("path", {
    d: "m21 21-4.3-4.3"
  })),
  bell: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M10.3 21a1.94 1.94 0 0 0 3.4 0"
  })),
  plus: /*#__PURE__*/React.createElement("path", {
    d: "M5 12h14M12 5v14"
  }),
  check: /*#__PURE__*/React.createElement("path", {
    d: "M20 6 9 17l-5-5"
  }),
  chart: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M3 3v16a2 2 0 0 0 2 2h16"
  }), /*#__PURE__*/React.createElement("path", {
    d: "m19 9-5 5-4-4-3 3"
  })),
  folder: /*#__PURE__*/React.createElement("path", {
    d: "M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"
  }),
  chevronDown: /*#__PURE__*/React.createElement("path", {
    d: "m6 9 6 6 6-6"
  }),
  chevronRight: /*#__PURE__*/React.createElement("path", {
    d: "m9 18 6-6-6-6"
  }),
  more: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("circle", {
    cx: "12",
    cy: "12",
    r: "1"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "19",
    cy: "12",
    r: "1"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "5",
    cy: "12",
    r: "1"
  })),
  arrowUpRight: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M7 7h10v10"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M7 17 17 7"
  })),
  x: /*#__PURE__*/React.createElement("path", {
    d: "M18 6 6 18M6 6l12 12"
  }),
  menu: /*#__PURE__*/React.createElement("path", {
    d: "M4 6h16M4 12h16M4 18h16"
  }),
  home: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M9 22V12h6v10"
  })),
  inbox: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("polyline", {
    points: "22 12 16 12 14 15 10 15 8 12 2 12"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"
  })),
  user: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "12",
    cy: "7",
    r: "4"
  }))
};
function Icon({
  name,
  size = 18,
  strokeWidth = 1.75,
  style
}) {
  return /*#__PURE__*/React.createElement("svg", {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: strokeWidth,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    style: {
      flexShrink: 0,
      ...style
    }
  }, P[name] || null);
}
Object.assign(__ds_scope, { Icon });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/display/Icon.jsx", error: String((e && e.message) || e) }); }

// components/display/Tag.jsx
try { (() => {
function Tag({
  onRemove,
  children,
  style
}) {
  const [hover, setHover] = React.useState(false);
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: "6px",
      padding: "4px 10px",
      borderRadius: "var(--radius-pill)",
      border: "1px solid var(--border-default)",
      background: "var(--surface-card)",
      font: "var(--type-caption)",
      color: "var(--text-body)",
      whiteSpace: "nowrap",
      ...style
    }
  }, children, onRemove && /*#__PURE__*/React.createElement("button", {
    onClick: onRemove,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      border: "none",
      background: "none",
      padding: 0,
      cursor: "pointer",
      display: "inline-flex",
      color: hover ? "var(--text-heading)" : "var(--text-muted)"
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: "12",
    height: "12",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2.5",
    strokeLinecap: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M18 6 6 18M6 6l12 12"
  }))));
}
Object.assign(__ds_scope, { Tag });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/display/Tag.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Dialog.jsx
try { (() => {
function Dialog({
  open = true,
  title,
  description,
  actions = null,
  onClose,
  width = 440,
  children,
  style
}) {
  if (!open) return null;
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClose,
    style: {
      position: "fixed",
      inset: 0,
      background: "rgba(20,20,19,.4)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 100
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    style: {
      width,
      maxWidth: "calc(100vw - 48px)",
      background: "var(--surface-raised)",
      borderRadius: "var(--radius-xl)",
      boxShadow: "var(--shadow-overlay)",
      padding: "var(--space-6)",
      animation: "lwDialogIn var(--dur-base) var(--ease-out)",
      ...style
    }
  }, /*#__PURE__*/React.createElement("style", null, "@keyframes lwDialogIn{from{opacity:0;transform:scale(.98)}to{opacity:1;transform:scale(1)}}"), title && /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-h3)",
      fontFamily: "var(--font-display)",
      color: "var(--text-heading)"
    }
  }, title), description && /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-body)",
      color: "var(--text-body)",
      marginTop: "8px"
    }
  }, description), children && /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: "16px"
    }
  }, children), actions && /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "flex-end",
      gap: "10px",
      marginTop: "24px"
    }
  }, actions)));
}
Object.assign(__ds_scope, { Dialog });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Dialog.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Toast.jsx
try { (() => {
function Toast({
  tone = "neutral",
  title,
  description,
  onDismiss,
  style
}) {
  const icons = {
    neutral: null,
    positive: /*#__PURE__*/React.createElement("svg", {
      width: "16",
      height: "16",
      viewBox: "0 0 24 24",
      fill: "none",
      stroke: "var(--positive)",
      strokeWidth: "2",
      strokeLinecap: "round",
      strokeLinejoin: "round"
    }, /*#__PURE__*/React.createElement("path", {
      d: "m5 13 4 4L19 7"
    })),
    danger: /*#__PURE__*/React.createElement("svg", {
      width: "16",
      height: "16",
      viewBox: "0 0 24 24",
      fill: "none",
      stroke: "var(--danger)",
      strokeWidth: "2",
      strokeLinecap: "round"
    }, /*#__PURE__*/React.createElement("circle", {
      cx: "12",
      cy: "12",
      r: "9"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M12 8v4M12 16h.01"
    }))
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "flex-start",
      gap: "10px",
      width: "320px",
      background: "var(--surface-inverse)",
      color: "var(--text-inverse)",
      borderRadius: "var(--radius-lg)",
      boxShadow: "var(--shadow-raised)",
      padding: "12px 14px",
      animation: "lwToastIn var(--dur-base) var(--ease-out)",
      ...style
    }
  }, /*#__PURE__*/React.createElement("style", null, "@keyframes lwToastIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}"), icons[tone] && /*#__PURE__*/React.createElement("span", {
    style: {
      marginTop: "2px"
    }
  }, icons[tone]), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-label)"
    }
  }, title), description && /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-body-sm)",
      color: "var(--ink-4)",
      marginTop: "2px"
    }
  }, description)), onDismiss && /*#__PURE__*/React.createElement("button", {
    onClick: onDismiss,
    style: {
      border: "none",
      background: "none",
      padding: 0,
      cursor: "pointer",
      color: "var(--ink-5)",
      display: "inline-flex"
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: "14",
    height: "14",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M18 6 6 18M6 6l12 12"
  }))));
}
Object.assign(__ds_scope, { Toast });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Toast.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Tooltip.jsx
try { (() => {
function Tooltip({
  label,
  side = "top",
  children,
  style
}) {
  const [show, setShow] = React.useState(false);
  const pos = {
    top: {
      bottom: "calc(100% + 6px)",
      left: "50%",
      transform: "translateX(-50%)"
    },
    bottom: {
      top: "calc(100% + 6px)",
      left: "50%",
      transform: "translateX(-50%)"
    },
    left: {
      right: "calc(100% + 6px)",
      top: "50%",
      transform: "translateY(-50%)"
    },
    right: {
      left: "calc(100% + 6px)",
      top: "50%",
      transform: "translateY(-50%)"
    }
  };
  return /*#__PURE__*/React.createElement("span", {
    onMouseEnter: () => setShow(true),
    onMouseLeave: () => setShow(false),
    style: {
      position: "relative",
      display: "inline-flex",
      ...style
    }
  }, children, show && /*#__PURE__*/React.createElement("span", {
    style: {
      position: "absolute",
      ...pos[side],
      background: "var(--surface-inverse)",
      color: "var(--text-inverse)",
      font: "var(--type-caption)",
      padding: "5px 10px",
      borderRadius: "var(--radius-sm)",
      whiteSpace: "nowrap",
      zIndex: 50,
      pointerEvents: "none"
    }
  }, label));
}
Object.assign(__ds_scope, { Tooltip });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Tooltip.jsx", error: String((e && e.message) || e) }); }

// components/forms/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Button({
  variant = "primary",
  size = "md",
  disabled = false,
  icon = null,
  children,
  onClick,
  style,
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const [press, setPress] = React.useState(false);
  const h = {
    sm: "var(--control-h-sm)",
    md: "var(--control-h-md)",
    lg: "var(--control-h-lg)"
  }[size];
  const px = {
    sm: "var(--control-pad-x-sm)",
    md: "var(--control-pad-x-md)",
    lg: "var(--control-pad-x-lg)"
  }[size];
  const fs = {
    sm: "13px",
    md: "14px",
    lg: "15px"
  }[size];
  const variants = {
    primary: {
      background: press ? "var(--interactive-press)" : hover ? "var(--interactive-hover)" : "var(--interactive)",
      color: "var(--text-inverse)",
      border: "none"
    },
    secondary: {
      background: press ? "rgba(20,20,19,.05)" : hover ? "rgba(20,20,19,.025)" : "var(--surface-card)",
      color: "var(--text-heading)",
      border: "1px solid var(--border-default)"
    },
    ghost: {
      background: press ? "rgba(20,20,19,.05)" : hover ? "rgba(20,20,19,.025)" : "transparent",
      color: "var(--ink-9)",
      border: "none"
    },
    danger: {
      background: press ? "#8c2f25" : hover ? "#b04a3f" : "var(--danger)",
      color: "#fff",
      border: "none"
    }
  };
  const disabledStyle = {
    background: "var(--ink-1)",
    color: "var(--ink-5)",
    border: "1px solid var(--border-subtle)"
  };
  return /*#__PURE__*/React.createElement("button", _extends({
    disabled: disabled,
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => {
      setHover(false);
      setPress(false);
    },
    onMouseDown: () => setPress(true),
    onMouseUp: () => setPress(false),
    style: {
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      gap: "8px",
      height: h,
      padding: `0 ${px}`,
      borderRadius: "var(--radius-md)",
      font: `600 ${fs}/1 var(--font-body)`,
      cursor: disabled ? "not-allowed" : "pointer",
      transition: "background var(--dur-fast) var(--ease-out)",
      whiteSpace: "nowrap",
      ...(disabled ? disabledStyle : variants[variant]),
      ...style
    }
  }, rest), icon, children);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Button.jsx", error: String((e && e.message) || e) }); }

// components/forms/Checkbox.jsx
try { (() => {
function Checkbox({
  label,
  checked,
  defaultChecked = false,
  onChange,
  disabled = false,
  style
}) {
  const [internal, setInternal] = React.useState(defaultChecked);
  const isOn = checked !== undefined ? checked : internal;
  const toggle = () => {
    if (disabled) return;
    const v = !isOn;
    if (checked === undefined) setInternal(v);
    onChange && onChange(v);
  };
  return /*#__PURE__*/React.createElement("label", {
    onClick: toggle,
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: "10px",
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.45 : 1,
      font: "var(--type-body-sm)",
      color: "var(--text-heading)",
      userSelect: "none",
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: "18px",
      height: "18px",
      borderRadius: "5px",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      background: isOn ? "var(--interactive)" : "var(--surface-card)",
      border: isOn ? "1px solid var(--interactive)" : "1px solid var(--border-default)",
      transition: "background var(--dur-fast) var(--ease-out)"
    }
  }, isOn && /*#__PURE__*/React.createElement("svg", {
    width: "12",
    height: "12",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "var(--text-inverse)",
    strokeWidth: "3",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "m5 13 4 4L19 7"
  }))), label);
}
Object.assign(__ds_scope, { Checkbox });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Checkbox.jsx", error: String((e && e.message) || e) }); }

// components/forms/IconButton.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function IconButton({
  size = "md",
  variant = "ghost",
  disabled = false,
  label,
  children,
  onClick,
  style,
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const d = {
    sm: "32px",
    md: "40px",
    lg: "48px"
  }[size];
  const variants = {
    ghost: {
      background: hover ? "var(--ink-1)" : "transparent",
      color: "var(--text-heading)",
      border: "none"
    },
    outline: {
      background: hover ? "var(--ink-1)" : "var(--surface-card)",
      color: "var(--text-heading)",
      border: "1px solid var(--border-default)"
    },
    primary: {
      background: hover ? "var(--interactive-hover)" : "var(--interactive)",
      color: "var(--text-inverse)",
      border: "none"
    }
  };
  return /*#__PURE__*/React.createElement("button", _extends({
    "aria-label": label,
    title: label,
    disabled: disabled,
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      width: d,
      height: d,
      borderRadius: "var(--radius-md)",
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.45 : 1,
      transition: "background var(--dur-fast) var(--ease-out)",
      ...variants[variant],
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { IconButton });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/IconButton.jsx", error: String((e && e.message) || e) }); }

// components/forms/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Input({
  label,
  hint,
  error,
  size = "md",
  prefix = null,
  suffix = null,
  style,
  inputStyle,
  ...rest
}) {
  const [focus, setFocus] = React.useState(false);
  const h = {
    sm: "var(--control-h-sm)",
    md: "var(--control-h-md)",
    lg: "var(--control-h-lg)"
  }[size];
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: "6px",
      font: "var(--type-label)",
      color: "var(--text-heading)",
      ...style
    }
  }, label, /*#__PURE__*/React.createElement("span", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: "8px",
      height: h,
      padding: "0 12px",
      background: "var(--surface-card)",
      border: `1px solid ${error ? "var(--danger)" : focus ? "var(--border-strong)" : "var(--border-default)"}`,
      borderRadius: "var(--radius-md)",
      boxShadow: focus ? "var(--shadow-focus)" : "none",
      transition: "box-shadow var(--dur-fast) var(--ease-out)"
    }
  }, prefix, /*#__PURE__*/React.createElement("input", _extends({
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      flex: 1,
      border: "none",
      outline: "none",
      background: "transparent",
      font: "var(--type-body)",
      color: "var(--text-heading)",
      minWidth: 0,
      ...inputStyle
    }
  }, rest)), suffix), error ? /*#__PURE__*/React.createElement("span", {
    style: {
      font: "var(--type-caption)",
      color: "var(--danger)",
      fontWeight: 400
    }
  }, error) : hint ? /*#__PURE__*/React.createElement("span", {
    style: {
      font: "var(--type-caption)",
      color: "var(--text-muted)",
      fontWeight: 400
    }
  }, hint) : null);
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Input.jsx", error: String((e && e.message) || e) }); }

// components/forms/Radio.jsx
try { (() => {
function Radio({
  options = [],
  value,
  defaultValue,
  onChange,
  name,
  disabled = false,
  style
}) {
  const [internal, setInternal] = React.useState(defaultValue);
  const sel = value !== undefined ? value : internal;
  const pick = v => {
    if (disabled) return;
    if (value === undefined) setInternal(v);
    onChange && onChange(v);
  };
  return /*#__PURE__*/React.createElement("div", {
    role: "radiogroup",
    style: {
      display: "flex",
      flexDirection: "column",
      gap: "10px",
      ...style
    }
  }, options.map(o => {
    const opt = typeof o === "string" ? {
      value: o,
      label: o
    } : o;
    const on = sel === opt.value;
    return /*#__PURE__*/React.createElement("label", {
      key: opt.value,
      onClick: () => pick(opt.value),
      style: {
        display: "inline-flex",
        alignItems: "center",
        gap: "10px",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.45 : 1,
        font: "var(--type-body-sm)",
        color: "var(--text-heading)",
        userSelect: "none"
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: "18px",
        height: "18px",
        borderRadius: "50%",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        border: on ? "1px solid var(--interactive)" : "1px solid var(--border-default)",
        background: "var(--surface-card)",
        transition: "border-color var(--dur-fast) var(--ease-out)"
      }
    }, on && /*#__PURE__*/React.createElement("span", {
      style: {
        width: "10px",
        height: "10px",
        borderRadius: "50%",
        background: "var(--interactive)"
      }
    })), opt.label);
  }));
}
Object.assign(__ds_scope, { Radio });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Radio.jsx", error: String((e && e.message) || e) }); }

// components/forms/Select.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Select({
  label,
  hint,
  options = [],
  size = "md",
  style,
  ...rest
}) {
  const [focus, setFocus] = React.useState(false);
  const h = {
    sm: "var(--control-h-sm)",
    md: "var(--control-h-md)",
    lg: "var(--control-h-lg)"
  }[size];
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: "6px",
      font: "var(--type-label)",
      color: "var(--text-heading)",
      ...style
    }
  }, label, /*#__PURE__*/React.createElement("span", {
    style: {
      position: "relative",
      display: "flex",
      height: h
    }
  }, /*#__PURE__*/React.createElement("select", _extends({
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      flex: 1,
      appearance: "none",
      WebkitAppearance: "none",
      padding: "0 36px 0 12px",
      background: "var(--surface-card)",
      border: `1px solid ${focus ? "var(--border-strong)" : "var(--border-default)"}`,
      borderRadius: "var(--radius-md)",
      boxShadow: focus ? "var(--shadow-focus)" : "none",
      font: "var(--type-body)",
      color: "var(--text-heading)",
      cursor: "pointer",
      outline: "none"
    }
  }, rest), options.map(o => typeof o === "string" ? /*#__PURE__*/React.createElement("option", {
    key: o,
    value: o
  }, o) : /*#__PURE__*/React.createElement("option", {
    key: o.value,
    value: o.value
  }, o.label))), /*#__PURE__*/React.createElement("svg", {
    width: "16",
    height: "16",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.75",
    style: {
      position: "absolute",
      right: "12px",
      top: "50%",
      transform: "translateY(-50%)",
      pointerEvents: "none",
      color: "var(--text-muted)"
    }
  }, /*#__PURE__*/React.createElement("path", {
    d: "m6 9 6 6 6-6"
  }))), hint && /*#__PURE__*/React.createElement("span", {
    style: {
      font: "var(--type-caption)",
      color: "var(--text-muted)",
      fontWeight: 400
    }
  }, hint));
}
Object.assign(__ds_scope, { Select });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Select.jsx", error: String((e && e.message) || e) }); }

// components/forms/Switch.jsx
try { (() => {
function Switch({
  label,
  checked,
  defaultChecked = false,
  onChange,
  disabled = false,
  style
}) {
  const [internal, setInternal] = React.useState(defaultChecked);
  const isOn = checked !== undefined ? checked : internal;
  const toggle = () => {
    if (disabled) return;
    const v = !isOn;
    if (checked === undefined) setInternal(v);
    onChange && onChange(v);
  };
  return /*#__PURE__*/React.createElement("label", {
    onClick: toggle,
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: "10px",
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.45 : 1,
      font: "var(--type-body-sm)",
      color: "var(--text-heading)",
      userSelect: "none",
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: "36px",
      height: "22px",
      borderRadius: "var(--radius-pill)",
      padding: "2px",
      boxSizing: "border-box",
      background: isOn ? "var(--interactive)" : "var(--ink-3)",
      transition: "background var(--dur-base) var(--ease-out)",
      display: "inline-flex"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: "18px",
      height: "18px",
      borderRadius: "50%",
      background: "#fff",
      transform: isOn ? "translateX(14px)" : "translateX(0)",
      transition: "transform var(--dur-base) var(--ease-out)",
      boxShadow: "0 1px 2px rgba(20,20,19,.2)"
    }
  })), label);
}
Object.assign(__ds_scope, { Switch });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Switch.jsx", error: String((e && e.message) || e) }); }

// components/navigation/Tabs.jsx
try { (() => {
function Tabs({
  tabs = [],
  value,
  defaultValue,
  onChange,
  variant = "underline",
  style
}) {
  const [internal, setInternal] = React.useState(defaultValue ?? (typeof tabs[0] === "string" ? tabs[0] : tabs[0]?.value));
  const sel = value !== undefined ? value : internal;
  const pick = v => {
    if (value === undefined) setInternal(v);
    onChange && onChange(v);
  };
  const norm = tabs.map(t => typeof t === "string" ? {
    value: t,
    label: t
  } : t);
  if (variant === "segmented") {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        display: "inline-flex",
        gap: "2px",
        padding: "5px",
        background: "var(--ink-1)",
        borderRadius: "var(--radius-md)",
        ...style
      }
    }, norm.map(t => /*#__PURE__*/React.createElement("button", {
      key: t.value,
      onClick: () => pick(t.value),
      style: {
        border: "none",
        cursor: "pointer",
        padding: "6px 14px",
        borderRadius: "var(--radius-sm)",
        font: "var(--type-label)",
        color: sel === t.value ? "var(--text-heading)" : "var(--text-muted)",
        background: sel === t.value ? "var(--surface-card)" : "transparent",
        boxShadow: sel === t.value ? "var(--shadow-card)" : "none",
        transition: "all var(--dur-fast) var(--ease-out)"
      }
    }, t.label)));
  }
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: "4px",
      borderBottom: "1px solid var(--border-subtle)",
      ...style
    }
  }, norm.map(t => /*#__PURE__*/React.createElement("button", {
    key: t.value,
    onClick: () => pick(t.value),
    style: {
      border: "none",
      background: "none",
      cursor: "pointer",
      padding: "10px 14px",
      font: "var(--type-label)",
      color: sel === t.value ? "var(--text-heading)" : "var(--text-muted)",
      boxShadow: sel === t.value ? "inset 0 -2px 0 var(--border-strong)" : "none",
      marginBottom: "-1px",
      transition: "color var(--dur-fast) var(--ease-out)"
    }
  }, t.label)));
}
Object.assign(__ds_scope, { Tabs });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/Tabs.jsx", error: String((e && e.message) || e) }); }

// ui_kits/dashboard/Overview.jsx
try { (() => {
const {
  Card,
  Badge,
  Tabs,
  Button,
  Icon
} = window.LeeworksDesignSystem_b3e560;
function Stat({
  label,
  value,
  delta,
  tone
}) {
  return /*#__PURE__*/React.createElement(Card, {
    padding: "var(--space-5)",
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-caption)",
      color: "var(--text-muted)"
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 28,
      fontWeight: 600,
      color: "var(--text-heading)",
      marginTop: 6
    }
  }, value), /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-caption)",
      color: tone === "up" ? "var(--positive)" : tone === "down" ? "var(--danger)" : "var(--text-muted)",
      marginTop: 4
    }
  }, delta));
}
function Bars() {
  const vals = [38, 52, 44, 61, 58, 70, 66, 79, 74, 88, 82, 95];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "flex-end",
      gap: 10,
      height: 160,
      padding: "8px 0"
    }
  }, vals.map((v, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      flex: 1,
      display: "flex",
      flexDirection: "column",
      gap: 6,
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: "100%",
      height: `${v}%`,
      background: i === 11 ? "var(--ink-9)" : "var(--ink-2)",
      borderRadius: "4px 4px 0 0",
      transition: "height var(--dur-slow) var(--ease-out)"
    }
  }))));
}
function Overview({
  onNew
}) {
  const activity = [["SR", "Sam Rivera", "published", "Q3 launch readiness", "2m ago"], ["JK", "Jae Kim", "commented on", "Mobile refresh scope", "18m ago"], ["AP", "Ana Petrova", "created", "Docs rewrite plan", "1h ago"], ["SR", "Sam Rivera", "invited", "2 people to Q3 launch", "3h ago"]];
  return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 12,
      marginBottom: 24
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("h2", {
    style: {
      font: "var(--type-h2)",
      letterSpacing: "var(--tracking-tight)",
      color: "var(--text-heading)",
      margin: 0
    }
  }, "Good morning, Sam"), /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-body-sm)",
      color: "var(--text-muted)",
      marginTop: 4
    }
  }, "Everything your team shipped this week, in one place.")), /*#__PURE__*/React.createElement(Button, {
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "plus",
      size: 16
    }),
    onClick: onNew
  }, "New report")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 16,
      marginBottom: 16
    }
  }, /*#__PURE__*/React.createElement(Stat, {
    label: "Active users",
    value: "12,438",
    delta: "+4.2% this week",
    tone: "up"
  }), /*#__PURE__*/React.createElement(Stat, {
    label: "Reports shipped",
    value: "86",
    delta: "+12 this week",
    tone: "up"
  }), /*#__PURE__*/React.createElement(Stat, {
    label: "Open reviews",
    value: "14",
    delta: "\u22123 since Monday",
    tone: "up"
  }), /*#__PURE__*/React.createElement(Stat, {
    label: "Sync errors",
    value: "2",
    delta: "+1 today",
    tone: "down"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "2fr 1fr",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement(Card, {
    title: "Weekly activity",
    subtitle: "Reports shipped per week",
    actions: /*#__PURE__*/React.createElement(Tabs, {
      variant: "segmented",
      tabs: ["12w", "6m", "1y"],
      defaultValue: "12w"
    })
  }, /*#__PURE__*/React.createElement(Bars, null)), /*#__PURE__*/React.createElement(Card, {
    title: "Recent activity",
    padding: "var(--space-5)"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 14
    }
  }, activity.map(([init, name, verb, obj, when], i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: "flex",
      gap: 10,
      alignItems: "flex-start"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 26,
      height: 26,
      borderRadius: "50%",
      background: "var(--ink-1)",
      color: "var(--ink-7)",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      font: "600 10px/1 var(--font-display)",
      flexShrink: 0
    }
  }, init), /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-body-sm)",
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-heading)",
      fontWeight: 600
    }
  }, name), " ", verb, " ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-heading)"
    }
  }, obj), /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-caption)",
      color: "var(--text-muted)",
      marginTop: 2
    }
  }, when))))))));
}
window.LwOverview = Overview;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/dashboard/Overview.jsx", error: String((e && e.message) || e) }); }

// ui_kits/dashboard/Reports.jsx
try { (() => {
const {
  Card,
  Badge,
  Tag,
  Button,
  Icon,
  IconButton,
  Tabs,
  Input
} = window.LeeworksDesignSystem_b3e560;
function Reports({
  onNew
}) {
  const rows = [["Q3 launch readiness", "Q3 launch", ["launch", "priority"], "positive", "Active", "Sam Rivera", "2m ago"], ["Mobile refresh scope", "Mobile refresh", ["mobile"], "warning", "Pending", "Jae Kim", "18m ago"], ["Docs rewrite plan", "Docs rewrite", ["docs"], "positive", "Active", "Ana Petrova", "1h ago"], ["Churn analysis — June", "Q3 launch", ["data"], "neutral", "Draft", "Sam Rivera", "2d ago"], ["Onboarding funnel v2", "Mobile refresh", ["mobile", "data"], "danger", "Failed", "Jae Kim", "3d ago"]];
  const th = {
    textAlign: "left",
    font: "var(--type-caption)",
    color: "var(--text-muted)",
    fontWeight: 600,
    padding: "10px 16px",
    borderBottom: "1px solid var(--border-subtle)",
    whiteSpace: "nowrap"
  };
  const td = {
    padding: "12px 16px",
    borderBottom: "1px solid var(--border-subtle)",
    font: "var(--type-body-sm)",
    color: "var(--text-body)",
    verticalAlign: "middle"
  };
  return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 12,
      marginBottom: 20
    }
  }, /*#__PURE__*/React.createElement("h2", {
    style: {
      font: "var(--type-h2)",
      letterSpacing: "var(--tracking-tight)",
      color: "var(--text-heading)",
      margin: 0,
      flex: 1
    }
  }, "Reports"), /*#__PURE__*/React.createElement(Button, {
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "plus",
      size: 16
    }),
    onClick: onNew
  }, "New report")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 12,
      marginBottom: 16
    }
  }, /*#__PURE__*/React.createElement(Tabs, {
    tabs: ["All", "Active", "Drafts", "Archived"],
    defaultValue: "All",
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(Input, {
    placeholder: "Filter reports\u2026",
    size: "sm",
    style: {
      width: 220
    }
  })), /*#__PURE__*/React.createElement(Card, {
    padding: "0"
  }, /*#__PURE__*/React.createElement("table", {
    style: {
      width: "100%",
      borderCollapse: "collapse"
    }
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
    style: th
  }, "Report"), /*#__PURE__*/React.createElement("th", {
    style: th
  }, "Project"), /*#__PURE__*/React.createElement("th", {
    style: th
  }, "Tags"), /*#__PURE__*/React.createElement("th", {
    style: th
  }, "Status"), /*#__PURE__*/React.createElement("th", {
    style: th
  }, "Owner"), /*#__PURE__*/React.createElement("th", {
    style: th
  }, "Updated"), /*#__PURE__*/React.createElement("th", {
    style: th
  }))), /*#__PURE__*/React.createElement("tbody", null, rows.map(([name, proj, tags, tone, status, owner, when], i) => /*#__PURE__*/React.createElement("tr", {
    key: i
  }, /*#__PURE__*/React.createElement("td", {
    style: {
      ...td,
      color: "var(--text-heading)",
      fontWeight: 600
    }
  }, name), /*#__PURE__*/React.createElement("td", {
    style: td
  }, proj), /*#__PURE__*/React.createElement("td", {
    style: td
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      gap: 6
    }
  }, tags.map(t => /*#__PURE__*/React.createElement(Tag, {
    key: t
  }, t)))), /*#__PURE__*/React.createElement("td", {
    style: td
  }, /*#__PURE__*/React.createElement(Badge, {
    tone: tone
  }, status)), /*#__PURE__*/React.createElement("td", {
    style: td
  }, owner), /*#__PURE__*/React.createElement("td", {
    style: {
      ...td,
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      color: "var(--text-muted)"
    }
  }, when), /*#__PURE__*/React.createElement("td", {
    style: {
      ...td,
      textAlign: "right"
    }
  }, /*#__PURE__*/React.createElement(IconButton, {
    label: "More",
    size: "sm"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "more",
    size: 16
  }))))))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "10px 16px",
      font: "var(--type-caption)",
      color: "var(--text-muted)"
    }
  }, "5 of 86 reports")));
}
window.LwReports = Reports;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/dashboard/Reports.jsx", error: String((e && e.message) || e) }); }

// ui_kits/dashboard/SettingsScreen.jsx
try { (() => {
const {
  Card,
  Button,
  Input,
  Select,
  Checkbox,
  Radio,
  Switch
} = window.LeeworksDesignSystem_b3e560;
function SettingsScreen({
  onSave
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "var(--content-max)"
    }
  }, /*#__PURE__*/React.createElement("h2", {
    style: {
      font: "var(--type-h2)",
      letterSpacing: "var(--tracking-tight)",
      color: "var(--text-heading)",
      margin: "0 0 20px"
    }
  }, "Workspace settings"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement(Card, {
    title: "General",
    padding: "var(--space-6)"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement(Input, {
    label: "Workspace name",
    defaultValue: "Acme Inc",
    hint: "Shown in the sidebar and on invites."
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement(Select, {
    label: "Default role for invites",
    options: ["Editor", "Admin", "Viewer"],
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(Select, {
    label: "Week starts on",
    options: ["Monday", "Sunday"],
    style: {
      flex: 1
    }
  })), /*#__PURE__*/React.createElement(Switch, {
    label: "Public workspace"
  }))), /*#__PURE__*/React.createElement(Card, {
    title: "Notifications",
    subtitle: "What we email you about",
    padding: "var(--space-6)"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 40
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(Checkbox, {
    label: "Weekly summaries",
    defaultChecked: true
  }), /*#__PURE__*/React.createElement(Checkbox, {
    label: "Mentions",
    defaultChecked: true
  }), /*#__PURE__*/React.createElement(Checkbox, {
    label: "Report status changes"
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-label)",
      color: "var(--text-heading)",
      marginBottom: 10
    }
  }, "Digest frequency"), /*#__PURE__*/React.createElement(Radio, {
    options: ["Every day", "Weekly", "Never"],
    defaultValue: "Weekly"
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "flex-end",
      gap: 10
    }
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "secondary"
  }, "Cancel"), /*#__PURE__*/React.createElement(Button, {
    onClick: onSave
  }, "Save changes"))));
}
window.LwSettingsScreen = SettingsScreen;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/dashboard/SettingsScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/dashboard/Shell.jsx
try { (() => {
const {
  Icon,
  Tooltip,
  IconButton
} = window.LeeworksDesignSystem_b3e560;
function SideItem({
  icon,
  label,
  active,
  onClick
}) {
  const [hover, setHover] = React.useState(false);
  return /*#__PURE__*/React.createElement("button", {
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      display: "flex",
      alignItems: "center",
      gap: 10,
      width: "100%",
      height: 36,
      padding: "0 10px",
      border: "none",
      cursor: "pointer",
      borderRadius: "var(--radius-md)",
      font: "var(--type-label)",
      textAlign: "left",
      color: active ? "var(--text-heading)" : "var(--text-muted)",
      background: active ? "var(--ink-2)" : hover ? "var(--ink-1)" : "transparent",
      transition: "background var(--dur-fast) var(--ease-out)"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: icon,
    size: 17
  }), label);
}
function Shell({
  screen,
  setScreen,
  children,
  onNotify
}) {
  const nav = [["overview", "dashboard", "Overview"], ["reports", "file", "Reports"], ["members", "users", "Members"], ["settings", "settings", "Settings"]];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      height: "100vh",
      background: "var(--surface-page)",
      font: "var(--type-body)",
      color: "var(--text-body)"
    }
  }, /*#__PURE__*/React.createElement("aside", {
    style: {
      width: 240,
      flexShrink: 0,
      background: "var(--surface-sunken)",
      borderRight: "1px solid var(--border-subtle)",
      display: "flex",
      flexDirection: "column",
      padding: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      padding: "4px 10px 20px"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: "800 20px/1 var(--font-display)",
      letterSpacing: "-0.03em",
      color: "var(--ink-9)"
    }
  }, "Leeworks")), /*#__PURE__*/React.createElement("nav", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 2
    }
  }, nav.map(([id, icon, label]) => /*#__PURE__*/React.createElement(SideItem, {
    key: id,
    icon: icon,
    label: label,
    active: screen === id,
    onClick: () => setScreen(id)
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 24,
      padding: "0 10px",
      font: "var(--type-overline)",
      letterSpacing: "var(--tracking-wide)",
      textTransform: "uppercase",
      color: "var(--ink-4)",
      fontSize: 11
    }
  }, "Projects"), /*#__PURE__*/React.createElement("nav", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 2,
      marginTop: 8
    }
  }, /*#__PURE__*/React.createElement(SideItem, {
    icon: "folder",
    label: "Q3 launch",
    onClick: () => setScreen("reports")
  }), /*#__PURE__*/React.createElement(SideItem, {
    icon: "folder",
    label: "Mobile refresh",
    onClick: () => setScreen("reports")
  }), /*#__PURE__*/React.createElement(SideItem, {
    icon: "folder",
    label: "Docs rewrite",
    onClick: () => setScreen("reports")
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: "auto",
      display: "flex",
      alignItems: "center",
      gap: 10,
      padding: 10,
      borderRadius: "var(--radius-md)",
      background: "var(--surface-card)",
      border: "1px solid var(--border-subtle)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 28,
      height: 28,
      borderRadius: "50%",
      background: "var(--ink-9)",
      color: "#fff",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      font: "600 12px/1 var(--font-display)"
    }
  }, "SR"), /*#__PURE__*/React.createElement("div", {
    style: {
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-label)",
      color: "var(--text-heading)",
      whiteSpace: "nowrap"
    }
  }, "Sam Rivera"), /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-caption)",
      color: "var(--text-muted)"
    }
  }, "Acme Inc")))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: "flex",
      flexDirection: "column",
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("header", {
    style: {
      height: 56,
      flexShrink: 0,
      display: "flex",
      alignItems: "center",
      gap: 8,
      padding: "0 24px",
      borderBottom: "1px solid var(--border-subtle)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      flex: 1,
      maxWidth: 360,
      height: 36,
      padding: "0 12px",
      border: "1px solid var(--border-default)",
      borderRadius: "var(--radius-md)",
      color: "var(--text-muted)"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "search",
    size: 16
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      font: "var(--type-body-sm)"
    }
  }, "Search projects, reports, people\u2026"), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: "auto",
      font: "var(--type-caption)",
      fontFamily: "var(--font-mono)",
      background: "var(--ink-1)",
      borderRadius: 4,
      padding: "2px 6px"
    }
  }, "\u2318K")), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: "auto",
      display: "flex",
      gap: 4
    }
  }, /*#__PURE__*/React.createElement(Tooltip, {
    label: "Notifications",
    side: "bottom"
  }, /*#__PURE__*/React.createElement(IconButton, {
    label: "Notifications",
    onClick: onNotify
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "bell",
    size: 18
  }))), /*#__PURE__*/React.createElement(Tooltip, {
    label: "Inbox",
    side: "bottom"
  }, /*#__PURE__*/React.createElement(IconButton, {
    label: "Inbox"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "inbox",
    size: 18
  }))))), /*#__PURE__*/React.createElement("main", {
    style: {
      flex: 1,
      overflow: "auto",
      padding: "28px 24px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "var(--page-max)",
      margin: "0 auto"
    }
  }, children))));
}
window.LwShell = Shell;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/dashboard/Shell.jsx", error: String((e && e.message) || e) }); }

// ui_kits/mobile/MHome.jsx
try { (() => {
const {
  Card,
  Badge,
  Icon,
  Button
} = window.LeeworksDesignSystem_b3e560;
function MHome({
  onNew
}) {
  const items = [["Q3 launch readiness", "positive", "Active", "2m ago"], ["Mobile refresh scope", "warning", "Pending", "18m ago"], ["Docs rewrite plan", "positive", "Active", "1h ago"], ["Churn analysis — June", "neutral", "Draft", "2d ago"]];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "8px 20px 20px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 12,
      margin: "12px 0 20px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-h3)",
      fontFamily: "var(--font-display)",
      letterSpacing: "var(--tracking-tight)",
      color: "var(--text-heading)"
    }
  }, "Good morning, Sam"), /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-body-sm)",
      color: "var(--text-muted)",
      marginTop: 2
    }
  }, "4 reports need your eyes")), /*#__PURE__*/React.createElement(Button, {
    size: "sm",
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "plus",
      size: 15
    }),
    onClick: onNew
  }, "New")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 12,
      marginBottom: 20
    }
  }, /*#__PURE__*/React.createElement(Card, {
    padding: "var(--space-4)",
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-caption)",
      color: "var(--text-muted)"
    }
  }, "Shipped"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 24,
      fontWeight: 600,
      color: "var(--text-heading)",
      marginTop: 4
    }
  }, "86")), /*#__PURE__*/React.createElement(Card, {
    padding: "var(--space-4)",
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-caption)",
      color: "var(--text-muted)"
    }
  }, "Reviews"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 24,
      fontWeight: 600,
      color: "var(--text-heading)",
      marginTop: 4
    }
  }, "14")), /*#__PURE__*/React.createElement(Card, {
    padding: "var(--space-4)",
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-caption)",
      color: "var(--text-muted)"
    }
  }, "Errors"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 24,
      fontWeight: 600,
      color: "var(--danger)",
      marginTop: 4
    }
  }, "2"))), /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-overline)",
      letterSpacing: "var(--tracking-wide)",
      textTransform: "uppercase",
      color: "var(--text-muted)",
      fontSize: 11,
      marginBottom: 10
    }
  }, "Recent reports"), /*#__PURE__*/React.createElement(Card, {
    padding: "0"
  }, items.map(([name, tone, status, when], i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: "flex",
      alignItems: "center",
      gap: 12,
      padding: "14px 16px",
      minHeight: 44,
      borderBottom: i < items.length - 1 ? "1px solid var(--border-subtle)" : "none"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-label)",
      color: "var(--text-heading)",
      whiteSpace: "nowrap",
      overflow: "hidden",
      textOverflow: "ellipsis"
    }
  }, name), /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-caption)",
      color: "var(--text-muted)",
      marginTop: 2
    }
  }, when)), /*#__PURE__*/React.createElement(Badge, {
    tone: tone
  }, status), /*#__PURE__*/React.createElement(Icon, {
    name: "chevronRight",
    size: 16,
    style: {
      color: "var(--ink-4)"
    }
  })))));
}
window.LwMHome = MHome;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/mobile/MHome.jsx", error: String((e && e.message) || e) }); }

// ui_kits/mobile/MInbox.jsx
try { (() => {
const {
  Card,
  Icon,
  Tabs
} = window.LeeworksDesignSystem_b3e560;
function MInbox() {
  const items = [["JK", "Jae Kim mentioned you", "\u201cCan you sanity-check the funnel numbers before Friday?\u201d", "18m", true], ["AP", "Ana requested review", "Docs rewrite plan · 6 pages", "1h", true], ["SR", "Sync completed", "Q3 launch · 3 sources updated", "3h", false], ["JK", "Jae approved your report", "Mobile refresh scope", "1d", false]];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "8px 20px 20px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-h3)",
      fontFamily: "var(--font-display)",
      letterSpacing: "var(--tracking-tight)",
      color: "var(--text-heading)",
      margin: "12px 0 16px"
    }
  }, "Inbox"), /*#__PURE__*/React.createElement(Tabs, {
    variant: "segmented",
    tabs: ["All", "Mentions", "Reviews"],
    defaultValue: "All",
    style: {
      marginBottom: 16
    }
  }), /*#__PURE__*/React.createElement(Card, {
    padding: "0"
  }, items.map(([init, title, body, when, unread], i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: "flex",
      gap: 12,
      padding: "14px 16px",
      borderBottom: i < items.length - 1 ? "1px solid var(--border-subtle)" : "none",
      background: unread ? "var(--surface-card)" : "var(--surface-page)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 32,
      height: 32,
      borderRadius: "50%",
      background: "var(--ink-1)",
      color: "var(--ink-7)",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      font: "600 11px/1 var(--font-display)",
      flexShrink: 0
    }
  }, init), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "baseline",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: "var(--type-label)",
      color: "var(--text-heading)",
      flex: 1,
      whiteSpace: "nowrap",
      overflow: "hidden",
      textOverflow: "ellipsis"
    }
  }, title), /*#__PURE__*/React.createElement("span", {
    style: {
      font: "var(--type-caption)",
      color: "var(--text-muted)",
      fontFamily: "var(--font-mono)"
    }
  }, when)), /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-body-sm)",
      color: "var(--text-body)",
      marginTop: 2,
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap"
    }
  }, body)), unread && /*#__PURE__*/React.createElement("span", {
    style: {
      width: 8,
      height: 8,
      borderRadius: "50%",
      background: "var(--signal)",
      marginTop: 6,
      flexShrink: 0
    }
  })))));
}
window.LwMInbox = MInbox;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/mobile/MInbox.jsx", error: String((e && e.message) || e) }); }

// ui_kits/mobile/MProfile.jsx
try { (() => {
const {
  Card,
  Switch,
  Icon,
  Button
} = window.LeeworksDesignSystem_b3e560;
function MProfile() {
  const rows = [["user", "Account"], ["bell", "Notifications"], ["users", "Workspace members"], ["settings", "Preferences"]];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "8px 20px 20px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: "center",
      margin: "20px 0 24px"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 72,
      height: 72,
      borderRadius: "50%",
      background: "var(--ink-9)",
      color: "#fff",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      font: "600 24px/1 var(--font-display)"
    }
  }, "SR"), /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-h4)",
      fontFamily: "var(--font-display)",
      color: "var(--text-heading)",
      marginTop: 12
    }
  }, "Sam Rivera"), /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-body-sm)",
      color: "var(--text-muted)"
    }
  }, "sam@acme.co \xB7 Acme Inc")), /*#__PURE__*/React.createElement(Card, {
    padding: "0",
    style: {
      marginBottom: 16
    }
  }, rows.map(([icon, label], i) => /*#__PURE__*/React.createElement("div", {
    key: label,
    style: {
      display: "flex",
      alignItems: "center",
      gap: 12,
      padding: "14px 16px",
      minHeight: 44,
      borderBottom: i < rows.length - 1 ? "1px solid var(--border-subtle)" : "none",
      cursor: "pointer"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: icon,
    size: 18,
    style: {
      color: "var(--ink-6)"
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      font: "var(--type-label)",
      color: "var(--text-heading)"
    }
  }, label), /*#__PURE__*/React.createElement(Icon, {
    name: "chevronRight",
    size: 16,
    style: {
      color: "var(--ink-4)"
    }
  })))), /*#__PURE__*/React.createElement(Card, {
    padding: "var(--space-4)",
    style: {
      marginBottom: 24
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 14
    }
  }, /*#__PURE__*/React.createElement(Switch, {
    label: "Push notifications",
    defaultChecked: true
  }), /*#__PURE__*/React.createElement(Switch, {
    label: "Weekly summary email",
    defaultChecked: true
  }), /*#__PURE__*/React.createElement(Switch, {
    label: "Dark mode"
  }))), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    style: {
      width: "100%"
    }
  }, "Sign out"));
}
window.LwMProfile = MProfile;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/mobile/MProfile.jsx", error: String((e && e.message) || e) }); }

// ui_kits/mobile/MobileShell.jsx
try { (() => {
const {
  Icon
} = window.LeeworksDesignSystem_b3e560;
function MobileShell({
  tab,
  setTab,
  children
}) {
  const tabs = [["home", "home", "Home"], ["inbox", "inbox", "Inbox"], ["profile", "user", "Profile"]];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      width: 390,
      height: 844,
      background: "var(--surface-page)",
      borderRadius: 48,
      border: "1px solid var(--border-default)",
      boxShadow: "var(--shadow-overlay)",
      overflow: "hidden",
      display: "flex",
      flexDirection: "column",
      font: "var(--type-body)",
      color: "var(--text-body)",
      position: "relative"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: 54,
      flexShrink: 0,
      display: "flex",
      alignItems: "flex-end",
      justifyContent: "space-between",
      padding: "0 28px 6px",
      font: "600 14px/1 var(--font-body)",
      color: "var(--text-heading)"
    }
  }, /*#__PURE__*/React.createElement("span", null, "9:41"), /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      gap: 5,
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: "16",
    height: "12",
    viewBox: "0 0 16 12",
    fill: "currentColor"
  }, /*#__PURE__*/React.createElement("rect", {
    x: "0",
    y: "7",
    width: "3",
    height: "5",
    rx: "1"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "4.5",
    y: "5",
    width: "3",
    height: "7",
    rx: "1"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "9",
    y: "2.5",
    width: "3",
    height: "9.5",
    rx: "1"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "13",
    y: "0",
    width: "3",
    height: "12",
    rx: "1",
    opacity: ".35"
  })), /*#__PURE__*/React.createElement("svg", {
    width: "24",
    height: "12",
    viewBox: "0 0 24 12",
    fill: "none"
  }, /*#__PURE__*/React.createElement("rect", {
    x: "0.5",
    y: "0.5",
    width: "20",
    height: "11",
    rx: "3",
    stroke: "currentColor",
    opacity: ".4"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "2",
    y: "2",
    width: "14",
    height: "8",
    rx: "1.5",
    fill: "currentColor"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M22.5 4v4a2 2 0 0 0 0-4z",
    fill: "currentColor",
    opacity: ".4"
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflow: "auto",
      minHeight: 0
    }
  }, children), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 84,
      flexShrink: 0,
      borderTop: "1px solid var(--border-subtle)",
      background: "var(--surface-page)",
      display: "flex",
      padding: "8px 12px 24px"
    }
  }, tabs.map(([id, icon, label]) => /*#__PURE__*/React.createElement("button", {
    key: id,
    onClick: () => setTab(id),
    style: {
      flex: 1,
      border: "none",
      background: "none",
      cursor: "pointer",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      gap: 4,
      padding: "6px 0",
      color: tab === id ? "var(--text-heading)" : "var(--ink-4)",
      transition: "color var(--dur-fast) var(--ease-out)"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: icon,
    size: 22,
    strokeWidth: tab === id ? 2 : 1.75
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      font: "var(--type-caption)",
      fontWeight: tab === id ? 600 : 500
    }
  }, label)))), /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      bottom: 8,
      left: "50%",
      transform: "translateX(-50%)",
      width: 134,
      height: 5,
      borderRadius: 3,
      background: "var(--ink-9)",
      opacity: .9
    }
  }));
}
window.LwMobileShell = MobileShell;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/mobile/MobileShell.jsx", error: String((e && e.message) || e) }); }

// ui_kits/website/Features.jsx
try { (() => {
const {
  Card,
  Icon,
  Button
} = window.LeeworksDesignSystem_b3e560;
function Features() {
  const feats = [["chart", "Reports that write themselves", "Connect your tools once. Leeworks drafts the weekly summary; you edit and ship."], ["users", "Built for the whole team", "Everyone sees the same bright surface — no per-seat gymnastics, no stale copies."], ["folder", "Projects, not piles", "Docs, decisions, and data live next to the work they describe."], ["check", "Reviews without the chase", "Assign, remind, and resolve in one thread. No status meetings."], ["inbox", "One inbox for everything", "Mentions, approvals, and syncs in a single queue you can actually finish."], ["settings", "Yours to shape", "Roles, fields, and workflows bend to your team — not the other way round."]];
  return /*#__PURE__*/React.createElement("section", {
    id: "features",
    style: {
      borderTop: "1px solid var(--border-subtle)",
      padding: "72px 24px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "var(--page-max)",
      margin: "0 auto"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-overline)",
      letterSpacing: "var(--tracking-wide)",
      textTransform: "uppercase",
      color: "var(--text-muted)"
    }
  }, "Features"), /*#__PURE__*/React.createElement("h2", {
    style: {
      font: "var(--type-h1)",
      letterSpacing: "var(--tracking-tight)",
      color: "var(--text-heading)",
      margin: "12px 0 40px",
      maxWidth: 560
    }
  }, "Less noise. More shipped."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "repeat(3,1fr)",
      gap: 16
    }
  }, feats.map(([icon, title, body]) => /*#__PURE__*/React.createElement(Card, {
    key: title,
    padding: "var(--space-6)"
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      width: 40,
      height: 40,
      borderRadius: "var(--radius-md)",
      background: "var(--ink-1)",
      color: "var(--ink-8)",
      alignItems: "center",
      justifyContent: "center"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: icon,
    size: 20
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-h4)",
      color: "var(--text-heading)",
      marginTop: 16
    }
  }, title), /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-body-sm)",
      color: "var(--text-body)",
      marginTop: 8,
      textWrap: "pretty"
    }
  }, body)))), /*#__PURE__*/React.createElement("div", {
    id: "pricing",
    style: {
      marginTop: 72,
      border: "1px solid var(--border-subtle)",
      borderRadius: "var(--radius-xl)",
      padding: "48px 40px",
      display: "flex",
      alignItems: "center",
      gap: 24,
      background: "var(--surface-sunken)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("h3", {
    style: {
      font: "var(--type-h2)",
      letterSpacing: "var(--tracking-tight)",
      color: "var(--text-heading)",
      margin: 0
    }
  }, "Start free. Stay simple."), /*#__PURE__*/React.createElement("p", {
    style: {
      font: "var(--type-body)",
      color: "var(--text-body)",
      margin: "10px 0 0",
      maxWidth: 480
    }
  }, "Free for teams of 5, then $8 per person per month. Everything included \u2014 no tiers to decode.")), /*#__PURE__*/React.createElement(Button, {
    size: "lg"
  }, "Start free"))));
}
window.LwFeatures = Features;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/website/Features.jsx", error: String((e && e.message) || e) }); }

// ui_kits/website/Hero.jsx
try { (() => {
const {
  Button,
  Badge,
  Icon
} = window.LeeworksDesignSystem_b3e560;
function Hero() {
  return /*#__PURE__*/React.createElement("section", {
    id: "product",
    style: {
      padding: "96px 24px 72px",
      textAlign: "center"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 820,
      margin: "0 auto"
    }
  }, /*#__PURE__*/React.createElement(Badge, {
    tone: "positive",
    style: {
      marginBottom: 20
    }
  }, "New \xB7 Reports 2.0"), /*#__PURE__*/React.createElement("h1", {
    style: {
      font: "var(--type-display)",
      fontSize: 64,
      letterSpacing: "-0.03em",
      color: "var(--text-heading)",
      margin: 0,
      textWrap: "balance"
    }
  }, "Everything your team ships, in one place"), /*#__PURE__*/React.createElement("p", {
    style: {
      font: "var(--type-body)",
      fontSize: 19,
      color: "var(--text-body)",
      maxWidth: 560,
      margin: "20px auto 0",
      textWrap: "pretty"
    }
  }, "Leeworks keeps projects, docs, and reports on one bright surface. Invite your team, connect your tools, and see what ships \u2014 without the noise."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 12,
      justifyContent: "center",
      marginTop: 32
    }
  }, /*#__PURE__*/React.createElement(Button, {
    size: "lg"
  }, "Start free"), /*#__PURE__*/React.createElement(Button, {
    size: "lg",
    variant: "secondary",
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "arrowUpRight",
      size: 16
    })
  }, "Book a demo")), /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-caption)",
      color: "var(--text-muted)",
      marginTop: 14
    }
  }, "Free for teams of 5. No credit card.")), /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "var(--page-max)",
      margin: "64px auto 0",
      border: "1px solid var(--border-subtle)",
      borderRadius: "var(--radius-xl)",
      boxShadow: "var(--shadow-raised)",
      overflow: "hidden",
      background: "var(--surface-sunken)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: 36,
      display: "flex",
      alignItems: "center",
      gap: 6,
      padding: "0 14px",
      borderBottom: "1px solid var(--border-subtle)",
      background: "var(--surface-card)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 10,
      height: 10,
      borderRadius: "50%",
      background: "var(--ink-3)"
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 10,
      height: 10,
      borderRadius: "50%",
      background: "var(--ink-3)"
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 10,
      height: 10,
      borderRadius: "50%",
      background: "var(--ink-3)"
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 420,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      font: "var(--type-body-sm)",
      color: "var(--text-muted)"
    }
  }, "Product screenshot \u2014 drop in a capture of ui_kits/dashboard")));
}
window.LwHero = Hero;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/website/Hero.jsx", error: String((e && e.message) || e) }); }

// ui_kits/website/SiteFooter.jsx
try { (() => {
function SiteFooter() {
  const col = {
    display: "flex",
    flexDirection: "column",
    gap: 10,
    font: "var(--type-body-sm)"
  };
  const a = {
    color: "var(--ink-4)",
    textDecoration: "none"
  };
  const h = {
    font: "var(--type-overline)",
    letterSpacing: "var(--tracking-wide)",
    textTransform: "uppercase",
    color: "var(--ink-5)",
    fontSize: 11,
    marginBottom: 4
  };
  return /*#__PURE__*/React.createElement("footer", {
    id: "docs",
    style: {
      background: "var(--surface-inverse)",
      color: "var(--ink-4)",
      padding: "56px 24px 40px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "var(--page-max)",
      margin: "0 auto",
      display: "flex",
      gap: 64
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: "800 22px/1 var(--font-display)",
      letterSpacing: "-0.03em",
      color: "#fff"
    }
  }, "Leeworks"), /*#__PURE__*/React.createElement("div", {
    style: {
      font: "var(--type-body-sm)",
      marginTop: 12,
      maxWidth: 260
    }
  }, "Everything your team ships, in one place.")), /*#__PURE__*/React.createElement("div", {
    style: col
  }, /*#__PURE__*/React.createElement("div", {
    style: h
  }, "Product"), /*#__PURE__*/React.createElement("a", {
    style: a,
    href: "#features"
  }, "Features"), /*#__PURE__*/React.createElement("a", {
    style: a,
    href: "#pricing"
  }, "Pricing"), /*#__PURE__*/React.createElement("a", {
    style: a,
    href: "#"
  }, "Changelog")), /*#__PURE__*/React.createElement("div", {
    style: col
  }, /*#__PURE__*/React.createElement("div", {
    style: h
  }, "Company"), /*#__PURE__*/React.createElement("a", {
    style: a,
    href: "#"
  }, "About"), /*#__PURE__*/React.createElement("a", {
    style: a,
    href: "#"
  }, "Careers"), /*#__PURE__*/React.createElement("a", {
    style: a,
    href: "#"
  }, "Contact")), /*#__PURE__*/React.createElement("div", {
    style: col
  }, /*#__PURE__*/React.createElement("div", {
    style: h
  }, "Resources"), /*#__PURE__*/React.createElement("a", {
    style: a,
    href: "#"
  }, "Docs"), /*#__PURE__*/React.createElement("a", {
    style: a,
    href: "#"
  }, "API"), /*#__PURE__*/React.createElement("a", {
    style: a,
    href: "#"
  }, "Status"))), /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "var(--page-max)",
      margin: "40px auto 0",
      paddingTop: 20,
      borderTop: "1px solid var(--ink-8)",
      font: "var(--type-caption)",
      color: "var(--ink-6)"
    }
  }, "\xA9 2026 Leeworks Systems"));
}
window.LwSiteFooter = SiteFooter;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/website/SiteFooter.jsx", error: String((e && e.message) || e) }); }

// ui_kits/website/SiteNav.jsx
try { (() => {
const {
  Button
} = window.LeeworksDesignSystem_b3e560;
function SiteNav() {
  const link = {
    font: "var(--type-label)",
    color: "var(--text-body)",
    textDecoration: "none",
    padding: "8px 12px",
    borderRadius: "var(--radius-md)"
  };
  return /*#__PURE__*/React.createElement("nav", {
    style: {
      position: "sticky",
      top: 0,
      zIndex: 50,
      background: "rgba(255,255,255,.97)",
      borderBottom: "1px solid var(--border-subtle)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "var(--page-max)",
      margin: "0 auto",
      padding: "0 24px",
      height: 64,
      display: "flex",
      alignItems: "center",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: "800 22px/1 var(--font-display)",
      letterSpacing: "-0.03em",
      color: "var(--ink-9)",
      marginRight: 24
    }
  }, "Leeworks"), /*#__PURE__*/React.createElement("a", {
    href: "#product",
    style: link
  }, "Product"), /*#__PURE__*/React.createElement("a", {
    href: "#features",
    style: link
  }, "Features"), /*#__PURE__*/React.createElement("a", {
    href: "#pricing",
    style: link
  }, "Pricing"), /*#__PURE__*/React.createElement("a", {
    href: "#docs",
    style: link
  }, "Docs"), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: "auto",
      display: "flex",
      gap: 10,
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "ghost",
    size: "sm"
  }, "Sign in"), /*#__PURE__*/React.createElement(Button, {
    size: "sm"
  }, "Start free"))));
}
window.LwSiteNav = SiteNav;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/website/SiteNav.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.Icon = __ds_scope.Icon;

__ds_ns.Tag = __ds_scope.Tag;

__ds_ns.Dialog = __ds_scope.Dialog;

__ds_ns.Toast = __ds_scope.Toast;

__ds_ns.Tooltip = __ds_scope.Tooltip;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Checkbox = __ds_scope.Checkbox;

__ds_ns.IconButton = __ds_scope.IconButton;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.Radio = __ds_scope.Radio;

__ds_ns.Select = __ds_scope.Select;

__ds_ns.Switch = __ds_scope.Switch;

__ds_ns.Tabs = __ds_scope.Tabs;

})();
